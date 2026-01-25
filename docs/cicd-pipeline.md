# CI/CD Pipeline Guide

## Overview

GitHub Actions workflow for automated testing, building, and deployment of Barbossa.

## Pipeline Architecture

```
+------------+     +--------+     +---------+     +------------+
|   Commit   | --> |  Test  | --> |  Build  | --> |   Deploy   |
+------------+     +--------+     +---------+     +------------+
                       |              |                  |
                   Unit Tests    Docker Image      Staging/Prod
                   Lint/Format   Push to Registry
                   Type Check
```

## GitHub Actions Workflows

### Main CI/CD Workflow

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # ============================================
  # BACKEND TESTS
  # ============================================
  test-backend:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: barbossa_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg exiftool

      - name: Run linting
        run: |
          cd backend
          ruff check .
          ruff format --check .

      - name: Run type checking
        run: |
          cd backend
          mypy app --ignore-missing-imports

      - name: Run tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/barbossa_test
          REDIS_URL: redis://localhost:6379
        run: |
          cd backend
          pytest tests/ -v --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./backend/coverage.xml
          fail_ci_if_error: false

  # ============================================
  # FRONTEND TESTS
  # ============================================
  test-frontend:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run linting
        run: |
          cd frontend
          npm run lint

      - name: Run type checking
        run: |
          cd frontend
          npm run type-check

      - name: Run tests
        run: |
          cd frontend
          npm run test -- --coverage

      - name: Build
        run: |
          cd frontend
          npm run build

  # ============================================
  # SECURITY SCAN
  # ============================================
  security-scan:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          ignore-unfixed: true
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

  # ============================================
  # BUILD DOCKER IMAGES
  # ============================================
  build:
    needs: [test-backend, test-frontend]
    runs-on: ubuntu-latest
    if: github.event_name == 'push'

    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=sha,prefix=
            type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}

      - name: Build and push backend
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-backend:${{ steps.meta.outputs.version }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-frontend:${{ steps.meta.outputs.version }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ============================================
  # DEPLOY TO STAGING
  # ============================================
  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    environment: staging

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to staging
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.STAGING_HOST }}
          username: ${{ secrets.STAGING_USER }}
          key: ${{ secrets.STAGING_SSH_KEY }}
          script: |
            cd /opt/barbossa
            docker compose pull
            docker compose up -d
            docker compose exec -T barbossa python -m app.cli migrate
            docker system prune -f

  # ============================================
  # DEPLOY TO PRODUCTION
  # ============================================
  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to production
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/barbossa

            # Backup database before deploy
            docker compose exec -T db pg_dump -U barbossa barbossa > /backup/barbossa_$(date +%Y%m%d_%H%M%S).sql

            # Pull and deploy
            docker compose pull
            docker compose up -d

            # Run migrations
            docker compose exec -T barbossa python -m app.cli migrate

            # Health check
            sleep 10
            curl -f http://localhost:8080/api/health || exit 1

            # Cleanup
            docker system prune -f
```

### Database Migration Workflow

```yaml
# .github/workflows/migrations.yml
name: Database Migrations

on:
  push:
    paths:
      - 'backend/alembic/**'
    branches: [main, develop]

jobs:
  validate-migrations:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: barbossa_test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run migrations
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/barbossa_test
        run: |
          cd backend
          alembic upgrade head

      - name: Check for pending migrations
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/barbossa_test
        run: |
          cd backend
          alembic check
```

### Release Workflow

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate changelog
        id: changelog
        uses: orhun/git-cliff-action@v3
        with:
          config: cliff.toml
          args: --latest --strip header

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          body: ${{ steps.changelog.outputs.content }}
          draft: false
          prerelease: ${{ contains(github.ref, 'alpha') || contains(github.ref, 'beta') }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Development Requirements Files

### Backend Dev Dependencies

```txt
# backend/requirements-dev.txt
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
httpx>=0.24.0  # For TestClient
ruff>=0.1.0
mypy>=1.5.0
types-redis>=4.6.0
factory-boy>=3.3.0  # Test fixtures
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.0
    hooks:
      - id: mypy
        additional_dependencies: [types-redis]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1000']
```

## Docker Configuration

### Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    exiftool \
    mktorrent \
    mediainfo \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install streamrip and yt-dlp
RUN pip install --no-cache-dir streamrip yt-dlp beets

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
```

## Environment Configuration

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `STAGING_HOST` | Staging server hostname |
| `STAGING_USER` | SSH username for staging |
| `STAGING_SSH_KEY` | SSH private key for staging |
| `PROD_HOST` | Production server hostname |
| `PROD_USER` | SSH username for production |
| `PROD_SSH_KEY` | SSH private key for production |

### Environment Files

```bash
# .env.staging
DATABASE_URL=postgresql://barbossa:xxx@db/barbossa
REDIS_URL=redis://redis:6379
QOBUZ_EMAIL=xxx
QOBUZ_PASSWORD=xxx

# .env.production
DATABASE_URL=postgresql://barbossa:xxx@db/barbossa
REDIS_URL=redis://redis:6379
QOBUZ_EMAIL=xxx
QOBUZ_PASSWORD=xxx
```

## Deployment Server Setup

### Initial Server Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Create application directory
sudo mkdir -p /opt/barbossa
sudo chown $USER:$USER /opt/barbossa

# Clone repository
cd /opt/barbossa
git clone https://github.com/your-org/barbossa.git .

# Create docker-compose.override.yml for production settings
cat > docker-compose.override.yml << 'EOF'
version: '3.8'
services:
  barbossa:
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
  worker:
    restart: always
  frontend:
    restart: always
  db:
    restart: always
  redis:
    restart: always
EOF

# Start services
docker compose up -d
```

### Rollback Procedure

```bash
# Rollback to previous version
cd /opt/barbossa

# List available versions
docker images | grep barbossa

# Deploy specific version
export VERSION=sha-abc123
docker compose pull
docker compose up -d

# Or restore from backup if needed
docker compose exec -T db psql -U barbossa barbossa < /backup/barbossa_20240101_120000.sql
```

## Monitoring Integration

```yaml
# Add to docker-compose.yml for monitoring
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  grafana_data:
```
