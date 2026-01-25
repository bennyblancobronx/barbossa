# Monitoring & Logging Guide

## Overview

Comprehensive monitoring stack for Barbossa: metrics collection, log aggregation, alerting, and dashboards.

## Architecture

```
+-------------------+     +------------------+     +------------------+
|     Barbossa      |     |    Prometheus    |     |     Grafana      |
|  (FastAPI + Celery)|---->|  (Metrics Store) |---->|   (Dashboards)   |
+-------------------+     +------------------+     +------------------+
         |
         |  Logs
         v
+-------------------+     +------------------+     +------------------+
|     Filebeat      |---->|   Elasticsearch  |---->|      Kibana      |
|   (Log Shipper)   |     |   (Log Store)    |     |  (Log Analysis)  |
+-------------------+     +------------------+     +------------------+
         |
         v
+-------------------+
|    Alertmanager   |
|     (Alerts)      |
+-------------------+
```

## Metrics (Prometheus)

### Application Metrics

```python
# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info
import time

# Request metrics
REQUEST_COUNT = Counter(
    'barbossa_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'barbossa_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Download metrics
DOWNLOADS_TOTAL = Counter(
    'barbossa_downloads_total',
    'Total downloads',
    ['source', 'status']
)

DOWNLOAD_DURATION = Histogram(
    'barbossa_download_duration_seconds',
    'Download duration in seconds',
    ['source'],
    buckets=[10, 30, 60, 120, 300, 600, 1800]
)

ACTIVE_DOWNLOADS = Gauge(
    'barbossa_active_downloads',
    'Currently active downloads'
)

# Import metrics
IMPORTS_TOTAL = Counter(
    'barbossa_imports_total',
    'Total imports',
    ['status', 'source']
)

# Library metrics
LIBRARY_SIZE = Gauge(
    'barbossa_library_tracks_total',
    'Total tracks in library'
)

LIBRARY_SIZE_BYTES = Gauge(
    'barbossa_library_size_bytes',
    'Total library size in bytes'
)

# User metrics
ACTIVE_USERS = Gauge(
    'barbossa_active_users',
    'Currently active users'
)

WEBSOCKET_CONNECTIONS = Gauge(
    'barbossa_websocket_connections',
    'Active WebSocket connections'
)

# Queue metrics
CELERY_QUEUE_LENGTH = Gauge(
    'barbossa_celery_queue_length',
    'Celery queue length',
    ['queue']
)

# System info
APP_INFO = Info(
    'barbossa_app',
    'Application information'
)
APP_INFO.info({'version': '0.1.7', 'python_version': '3.11'})
```

### Middleware for Request Metrics

```python
# app/middleware/metrics.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY
import time

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        endpoint = request.url.path
        method = request.method
        status = response.status_code

        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status=status
        ).inc()

        REQUEST_LATENCY.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

        return response

# In main.py
app.add_middleware(MetricsMiddleware)
```

### Metrics Endpoint

```python
# app/api/metrics.py
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

router = APIRouter()

@router.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### Celery Metrics

```python
# app/celery_metrics.py
from celery.signals import task_prerun, task_postrun, task_failure
from app.metrics import CELERY_QUEUE_LENGTH
import time

task_start_times = {}

@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    task_start_times[task_id] = time.time()

@task_postrun.connect
def task_postrun_handler(task_id, task, *args, retval=None, state=None, **kwargs):
    if task_id in task_start_times:
        duration = time.time() - task_start_times.pop(task_id)
        # Record task duration metrics

@task_failure.connect
def task_failure_handler(task_id, exception, *args, **kwargs):
    # Record task failure metrics
    pass
```

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alerts/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'barbossa'
    static_configs:
      - targets: ['barbossa:8080']
    metrics_path: '/metrics'

  - job_name: 'celery'
    static_configs:
      - targets: ['worker:9808']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:9121']

  - job_name: 'postgres'
    static_configs:
      - targets: ['db:9187']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Alert Rules

```yaml
# prometheus/alerts/barbossa.yml
groups:
  - name: barbossa
    rules:
      - alert: HighErrorRate
        expr: rate(barbossa_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected
          description: "Error rate is {{ $value | humanize }}%"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(barbossa_request_latency_seconds_bucket[5m])) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: High request latency
          description: "95th percentile latency is {{ $value | humanize }}s"

      - alert: DownloadQueueBacklog
        expr: barbossa_celery_queue_length{queue="downloads"} > 50
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: Download queue backlog
          description: "{{ $value }} downloads waiting in queue"

      - alert: LowDiskSpace
        expr: (node_filesystem_avail_bytes{mountpoint="/music"} / node_filesystem_size_bytes{mountpoint="/music"}) < 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Low disk space on music volume
          description: "Only {{ $value | humanizePercentage }} space remaining"

      - alert: DatabaseConnectionFailure
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: Database connection lost
```

## Logging

### Structured Logging Setup

```python
# app/logging_config.py
import logging
import json
from datetime import datetime
from typing import Any
import sys

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)

        # Add request context if available
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id

        return json.dumps(log_data)

def setup_logging(level: str = 'INFO'):
    """Configure application logging."""

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console handler (JSON in production, readable in dev)
    console_handler = logging.StreamHandler(sys.stdout)

    if os.getenv('ENVIRONMENT') == 'production':
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        ))

    root_logger.addHandler(console_handler)

    # Silence noisy loggers
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)

# Context-aware logger
class ContextLogger:
    """Logger with request context."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._context = {}

    def bind(self, **kwargs) -> 'ContextLogger':
        """Add context that will be included in all log messages."""
        new_logger = ContextLogger(self.logger.name)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _log(self, level: int, message: str, **kwargs):
        extra = {**self._context, **kwargs}
        self.logger.log(level, message, extra={'extra': extra})

    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)

    def exception(self, message: str, **kwargs):
        self._log(logging.ERROR, message, exc_info=True, **kwargs)

# Usage
logger = ContextLogger('barbossa')
```

### Request ID Middleware

```python
# app/middleware/request_id.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import contextvars

request_id_var = contextvars.ContextVar('request_id', default=None)

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        request_id_var.set(request_id)

        response = await call_next(request)
        response.headers['X-Request-ID'] = request_id

        return response
```

### Log Aggregation (ELK Stack)

```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.11.0
    user: root
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - elasticsearch

volumes:
  elasticsearch_data:
```

### Filebeat Configuration

```yaml
# filebeat.yml
filebeat.inputs:
  - type: container
    paths:
      - '/var/lib/docker/containers/*/*.log'
    processors:
      - add_docker_metadata:
          host: "unix:///var/run/docker.sock"
      - decode_json_fields:
          fields: ["message"]
          target: "json"
          overwrite_keys: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  indices:
    - index: "barbossa-logs-%{+yyyy.MM.dd}"
      when.contains:
        docker.container.name: "barbossa"
    - index: "celery-logs-%{+yyyy.MM.dd}"
      when.contains:
        docker.container.name: "worker"

setup.kibana:
  host: "kibana:5601"
```

## Health Checks

### Health Endpoint

```python
# app/api/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
import redis.asyncio as redis
import httpx

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive health check."""
    checks = {}
    overall_healthy = True

    # Database check
    try:
        await db.execute("SELECT 1")
        checks['database'] = {'status': 'healthy'}
    except Exception as e:
        checks['database'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False

    # Redis check
    try:
        r = redis.from_url(REDIS_URL)
        await r.ping()
        checks['redis'] = {'status': 'healthy'}
    except Exception as e:
        checks['redis'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False

    # Plex check (optional)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PLEX_URL}/identity",
                params={"X-Plex-Token": PLEX_TOKEN},
                timeout=5
            )
            checks['plex'] = {'status': 'healthy' if response.status_code == 200 else 'degraded'}
    except Exception as e:
        checks['plex'] = {'status': 'degraded', 'error': str(e)}

    # Lidarr check (optional)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{LIDARR_URL}/api/v1/system/status",
                headers={"X-Api-Key": LIDARR_API_KEY},
                timeout=5
            )
            checks['lidarr'] = {'status': 'healthy' if response.status_code == 200 else 'degraded'}
    except Exception as e:
        checks['lidarr'] = {'status': 'degraded', 'error': str(e)}

    # Disk space check
    import shutil
    total, used, free = shutil.disk_usage('/music')
    free_percent = (free / total) * 100
    checks['disk'] = {
        'status': 'healthy' if free_percent > 10 else 'warning',
        'free_percent': round(free_percent, 1),
        'free_bytes': free
    }
    if free_percent < 5:
        overall_healthy = False

    return {
        'status': 'healthy' if overall_healthy else 'unhealthy',
        'checks': checks
    }

@router.get("/health/live")
async def liveness():
    """Kubernetes liveness probe."""
    return {'status': 'alive'}

@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Kubernetes readiness probe."""
    try:
        await db.execute("SELECT 1")
        return {'status': 'ready'}
    except Exception:
        return {'status': 'not ready'}, 503
```

## Grafana Dashboards

### Dashboard JSON (Import into Grafana)

```json
{
  "title": "Barbossa Overview",
  "panels": [
    {
      "title": "Request Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(barbossa_requests_total[5m])",
          "legendFormat": "{{method}} {{endpoint}}"
        }
      ]
    },
    {
      "title": "Request Latency (p95)",
      "type": "graph",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, rate(barbossa_request_latency_seconds_bucket[5m]))",
          "legendFormat": "{{endpoint}}"
        }
      ]
    },
    {
      "title": "Active Downloads",
      "type": "stat",
      "targets": [
        {
          "expr": "barbossa_active_downloads"
        }
      ]
    },
    {
      "title": "Download Queue",
      "type": "stat",
      "targets": [
        {
          "expr": "barbossa_celery_queue_length{queue=\"downloads\"}"
        }
      ]
    },
    {
      "title": "Library Size",
      "type": "stat",
      "targets": [
        {
          "expr": "barbossa_library_tracks_total"
        }
      ]
    },
    {
      "title": "Error Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(barbossa_requests_total{status=~\"5..\"}[5m])",
          "legendFormat": "5xx errors"
        }
      ]
    }
  ]
}
```

## Docker Compose Integration

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alerts:/etc/prometheus/alerts
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3001:3000"

  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
    ports:
      - "9093:9093"

  node-exporter:
    image: prom/node-exporter:latest
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'

  redis-exporter:
    image: oliver006/redis_exporter:latest
    environment:
      - REDIS_ADDR=redis://redis:6379

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    environment:
      - DATA_SOURCE_NAME=postgresql://barbossa:password@db:5432/barbossa?sslmode=disable

volumes:
  prometheus_data:
  grafana_data:
```

### Alertmanager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'

receivers:
  - name: 'default'
    email_configs:
      - to: 'admin@example.com'
        from: 'barbossa@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'barbossa@example.com'
        auth_password: '{{ .EmailPassword }}'

  - name: 'critical'
    email_configs:
      - to: 'admin@example.com'
    slack_configs:
      - api_url: '{{ .SlackWebhook }}'
        channel: '#alerts'
        title: '{{ .Status | toUpper }}: {{ .CommonAnnotations.summary }}'
        text: '{{ .CommonAnnotations.description }}'
```
