#!/bin/bash
# Barbossa Database Restore Script
set -e

if [ -z "$1" ]; then
    echo "Barbossa Database Restore"
    echo ""
    echo "Usage: restore.sh <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lah /backups/*.sql.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"

# Handle relative path
if [[ ! "$BACKUP_FILE" = /* ]]; then
    BACKUP_FILE="/backups/$BACKUP_FILE"
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will overwrite the current database!"
echo "Backup file: $BACKUP_FILE"
read -p "Continue? (y/N) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "Restoring database from: $BACKUP_FILE"

# Drop and recreate database
echo "Dropping existing database..."
psql -h db -U barbossa -d postgres -c "DROP DATABASE IF EXISTS barbossa;"
psql -h db -U barbossa -d postgres -c "CREATE DATABASE barbossa;"

# Restore
echo "Restoring data..."
gunzip -c "$BACKUP_FILE" | psql -h db -U barbossa -d barbossa

echo "Restore complete."
echo "You may need to restart the Barbossa services."
