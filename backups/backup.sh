#!/bin/bash
# Barbossa Database Backup Script
set -e

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

echo "Starting backup: ${DATE}"

# Database backup
echo "Backing up database..."
pg_dump -h db -U barbossa barbossa | gzip > "${BACKUP_DIR}/db_${DATE}.sql.gz"

# Config backup (beets, streamrip configs)
echo "Backing up configuration..."
if [ -d "/music/.barbossa" ]; then
    tar -czf "${BACKUP_DIR}/config_${DATE}.tar.gz" -C /music .barbossa 2>/dev/null || true
fi

# Clean old backups
echo "Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "*.gz" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

# List recent backups
echo ""
echo "Recent backups:"
ls -lah "${BACKUP_DIR}"/*.gz 2>/dev/null | tail -10 || echo "No backups found"

# Calculate total backup size
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1)
echo ""
echo "Total backup size: ${TOTAL_SIZE}"
echo "Backup complete: ${DATE}"
