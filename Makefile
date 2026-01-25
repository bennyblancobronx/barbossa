# Barbossa Music Library - Deployment Commands
# Version: 0.1.10

.PHONY: help build up down logs backup restore shell test lint \
        prod-build prod-up prod-down prod-logs ssl-generate db-migrate db-shell

COMPOSE_FILE ?= docker-compose.yml
COMPOSE_PROD_FILE = docker-compose.prod.yml

# Default target
help:
	@echo "Barbossa Music Library - Commands"
	@echo ""
	@echo "Development:"
	@echo "  make build      Build development containers"
	@echo "  make up         Start development environment"
	@echo "  make down       Stop containers"
	@echo "  make logs       View logs (follow)"
	@echo "  make shell      Open shell in API container"
	@echo "  make test       Run tests"
	@echo "  make lint       Run linter"
	@echo ""
	@echo "Production:"
	@echo "  make prod-build Build production containers"
	@echo "  make prod-up    Start production environment"
	@echo "  make prod-down  Stop production environment"
	@echo "  make prod-logs  View production logs"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate Run database migrations"
	@echo "  make db-shell   Open PostgreSQL shell"
	@echo "  make backup     Create database backup"
	@echo "  make restore    Restore from backup"
	@echo ""
	@echo "Setup:"
	@echo "  make ssl-generate  Generate self-signed SSL cert"
	@echo "  make validate      Validate environment config"
	@echo ""

# ==========================================================================
# Development Commands
# ==========================================================================

build:
	docker-compose -f $(COMPOSE_FILE) build

up:
	docker-compose -f $(COMPOSE_FILE) up -d

down:
	docker-compose -f $(COMPOSE_FILE) down

logs:
	docker-compose -f $(COMPOSE_FILE) logs -f

shell:
	docker-compose -f $(COMPOSE_FILE) exec barbossa /bin/sh

test:
	docker-compose -f $(COMPOSE_FILE) exec barbossa pytest -v

lint:
	docker-compose -f $(COMPOSE_FILE) exec barbossa ruff check app/ || true

# ==========================================================================
# Production Commands
# ==========================================================================

prod-build:
	docker-compose -f $(COMPOSE_PROD_FILE) build

prod-up: validate
	docker-compose -f $(COMPOSE_PROD_FILE) up -d

prod-down:
	docker-compose -f $(COMPOSE_PROD_FILE) down

prod-logs:
	docker-compose -f $(COMPOSE_PROD_FILE) logs -f

prod-restart:
	docker-compose -f $(COMPOSE_PROD_FILE) restart

prod-status:
	docker-compose -f $(COMPOSE_PROD_FILE) ps

# ==========================================================================
# Database Commands
# ==========================================================================

db-migrate:
	docker-compose -f $(COMPOSE_FILE) exec barbossa alembic upgrade head

db-shell:
	docker-compose -f $(COMPOSE_FILE) exec db psql -U barbossa

db-vacuum:
	docker-compose -f $(COMPOSE_PROD_FILE) exec db vacuumdb -U barbossa barbossa

# ==========================================================================
# Backup Commands
# ==========================================================================

backup:
	docker-compose -f $(COMPOSE_PROD_FILE) --profile backup run --rm backup /backups/backup.sh

restore:
	@echo "Available backups:"
	@ls -la backups/*.sql.gz 2>/dev/null || echo "No backups found"
	@echo ""
	@read -p "Enter backup filename: " file; \
	docker-compose -f $(COMPOSE_PROD_FILE) --profile backup run --rm backup /backups/restore.sh $$file

# ==========================================================================
# Setup Commands
# ==========================================================================

ssl-generate:
	@mkdir -p nginx/ssl
	openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
		-keyout nginx/ssl/key.pem \
		-out nginx/ssl/cert.pem \
		-subj "/CN=barbossa.local"
	@echo ""
	@echo "Self-signed certificate generated."
	@echo "Replace with real certificate for production."

validate:
	@python3 scripts/validate_env.py

init-dirs:
	@echo "Creating music directory structure..."
	@mkdir -p $(MUSIC_PATH)/library
	@mkdir -p $(MUSIC_PATH)/users
	@mkdir -p $(MUSIC_PATH)/downloads/qobuz
	@mkdir -p $(MUSIC_PATH)/downloads/lidarr
	@mkdir -p $(MUSIC_PATH)/downloads/youtube
	@mkdir -p $(MUSIC_PATH)/import/pending
	@mkdir -p $(MUSIC_PATH)/import/review
	@mkdir -p $(MUSIC_PATH)/export
	@echo "Done."

# ==========================================================================
# Health Checks
# ==========================================================================

health:
	@curl -s http://localhost:8080/health | python3 -m json.tool || echo "API not responding"

health-prod:
	@curl -sk https://localhost/health | python3 -m json.tool || echo "API not responding"

# ==========================================================================
# Cleanup
# ==========================================================================

clean:
	docker-compose -f $(COMPOSE_FILE) down -v
	docker system prune -f

clean-all:
	docker-compose -f $(COMPOSE_FILE) down -v
	docker-compose -f $(COMPOSE_PROD_FILE) down -v
	docker system prune -af
	@echo "WARNING: All Docker resources cleaned"
