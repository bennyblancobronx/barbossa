# Cloud Backup Integration (rclone)

## Overview

rclone provides cloud storage sync for offsite backups. Supports 70+ storage providers including Google Drive, Dropbox, S3, B2, and local/network paths.

## Installation

```bash
# macOS
brew install rclone

# Linux
curl https://rclone.org/install.sh | sudo bash

# Docker (already in base image)
apt-get install rclone
```

## Configuration

### Interactive Setup

```bash
rclone config
```

Creates `~/.config/rclone/rclone.conf` with remote definitions.

### Common Remotes for Music Backup

**Google Drive:**
```ini
[gdrive-backup]
type = drive
scope = drive
token = {"access_token":"...","token_type":"Bearer",...}
root_folder_id = <folder_id>  # Optional: specific folder
```

**Backblaze B2:**
```ini
[b2-backup]
type = b2
account = <account_id>
key = <application_key>
```

**AWS S3:**
```ini
[s3-backup]
type = s3
provider = AWS
access_key_id = <key>
secret_access_key = <secret>
region = us-east-1
```

**Local/NAS Path:**
```ini
[nas-backup]
type = local
```

## CLI Commands

### Sync (Mirror)

```bash
# Sync local to remote (mirror - deletes remote files not in source)
rclone sync /music/artists remote:barbossa-backup/library --progress

# Sync specific artist
rclone sync "/music/artists/Pink Floyd" "remote:barbossa-backup/library/Pink Floyd" --progress
```

### Copy (Additive)

```bash
# Copy new files only (does not delete)
rclone copy /music/artists remote:barbossa-backup/library --progress

# Copy with bandwidth limit (10MB/s)
rclone copy /music/artists remote:barbossa-backup/library --bwlimit 10M --progress
```

### Verify

```bash
# Check for differences without transferring
rclone check /music/artists remote:barbossa-backup/library

# Verify checksums
rclone check /music/artists remote:barbossa-backup/library --checksum
```

### List

```bash
# List remote contents
rclone ls remote:barbossa-backup/library

# List with size
rclone lsl remote:barbossa-backup/library

# Tree view
rclone tree remote:barbossa-backup/library --max-depth 2
```

## Barbossa Integration

### Configuration (barbossa.yml)

```yaml
backup:
  enabled: true
  destinations:
    - type: local
      path: /backup/music
      schedule: daily
    - type: rclone
      remote: b2-backup
      path: barbossa-backup/library
      schedule: weekly
      options:
        bwlimit: "50M"
        transfers: 4
        checkers: 8
  verify_after: true
  retention:
    daily: 7
    weekly: 4
    monthly: 12
```

### Backup Service

```python
import subprocess
from datetime import datetime
from pathlib import Path

class RcloneBackupService:
    def __init__(self, config: dict):
        self.remote = config['remote']
        self.path = config['path']
        self.options = config.get('options', {})

    def sync(self, source: str, dry_run: bool = False) -> dict:
        """Sync local path to remote."""
        cmd = [
            'rclone', 'sync',
            source,
            f"{self.remote}:{self.path}",
            '--progress',
            '--stats-one-line',
            '--log-level', 'INFO'
        ]

        # Add options
        if self.options.get('bwlimit'):
            cmd.extend(['--bwlimit', self.options['bwlimit']])
        if self.options.get('transfers'):
            cmd.extend(['--transfers', str(self.options['transfers'])])
        if self.options.get('checkers'):
            cmd.extend(['--checkers', str(self.options['checkers'])])

        if dry_run:
            cmd.append('--dry-run')

        result = subprocess.run(cmd, capture_output=True, text=True)

        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }

    def verify(self, source: str) -> dict:
        """Verify backup integrity."""
        cmd = [
            'rclone', 'check',
            source,
            f"{self.remote}:{self.path}",
            '--checksum'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse differences
        differences = []
        for line in result.stderr.split('\n'):
            if 'ERROR' in line or 'NOTICE' in line:
                differences.append(line)

        return {
            'verified': result.returncode == 0,
            'differences': differences
        }

    def get_stats(self) -> dict:
        """Get remote storage stats."""
        cmd = ['rclone', 'about', f"{self.remote}:"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse output
        stats = {}
        for line in result.stdout.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                stats[key.strip().lower()] = value.strip()

        return stats
```

### Celery Task

```python
@celery.task(queue='maintenance')
def backup_to_cloud(destination_config: dict, full: bool = False):
    """Run scheduled cloud backup."""
    service = RcloneBackupService(destination_config)

    started = datetime.now()

    # Record in database
    backup_id = db.create_backup_record(
        destination=f"{destination_config['remote']}:{destination_config['path']}",
        status='running',
        started_at=started
    )

    try:
        # Run sync
        result = service.sync('/music/artists')

        if not result['success']:
            raise Exception(result['stderr'])

        # Verify if configured
        if destination_config.get('verify_after'):
            verify = service.verify('/music/artists')
            if not verify['verified']:
                raise Exception(f"Verification failed: {verify['differences']}")

        # Update record
        db.update_backup_record(
            backup_id,
            status='complete',
            completed_at=datetime.now()
        )

    except Exception as e:
        db.update_backup_record(
            backup_id,
            status='failed',
            error_message=str(e),
            completed_at=datetime.now()
        )
        raise
```

### Scheduled Backup (Celery Beat)

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'daily-local-backup': {
        'task': 'backup_to_local',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
    'weekly-cloud-backup': {
        'task': 'backup_to_cloud',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),  # Sunday 4 AM
        'kwargs': {'destination_config': CLOUD_BACKUP_CONFIG}
    },
}
```

## Restore Procedures

### Full Restore

```bash
# Restore entire library
rclone sync remote:barbossa-backup/library /music/artists --progress

# Verify after restore
rclone check remote:barbossa-backup/library /music/artists --checksum
```

### Partial Restore

```bash
# Restore single artist
rclone copy "remote:barbossa-backup/library/Pink Floyd" "/music/artists/Pink Floyd" --progress

# Restore single album
rclone copy "remote:barbossa-backup/library/Pink Floyd/The Dark Side of the Moon (1973)" \
  "/music/artists/Pink Floyd/The Dark Side of the Moon (1973)" --progress
```

## Performance Tuning

### Large Libraries (10,000+ albums)

```bash
rclone sync /music/artists remote:barbossa-backup/library \
  --transfers 8 \           # Parallel file transfers
  --checkers 16 \           # Parallel hash checkers
  --buffer-size 64M \       # Memory buffer per transfer
  --drive-chunk-size 64M \  # Google Drive chunk size
  --fast-list \             # Use fewer API calls (requires remote support)
  --progress
```

### Bandwidth Management

```bash
# Limit to 50MB/s
rclone sync /music/artists remote:barbossa-backup/library --bwlimit 50M

# Time-based limits (full speed 1AM-6AM, 10MB/s otherwise)
rclone sync /music/artists remote:barbossa-backup/library \
  --bwlimit "01:00,off 06:00,10M"
```

### Exclude Patterns

```bash
# Exclude temp files and caches
rclone sync /music/artists remote:barbossa-backup/library \
  --exclude "*.tmp" \
  --exclude ".DS_Store" \
  --exclude "Thumbs.db" \
  --exclude "*.partial"
```

## Encryption (Optional)

### Encrypted Remote

```bash
rclone config

# Create crypt remote wrapping existing remote
name> crypt-backup
Storage> crypt
Remote to encrypt/decrypt> b2-backup:barbossa-backup
filename_encryption> standard
directory_name_encryption> true
Password or pass phrase for encryption> [enter strong password]
Password or pass phrase for salt> [enter different password]
```

Usage:
```bash
# Backup (encrypted)
rclone sync /music/artists crypt-backup:/library --progress

# Restore (auto-decrypts)
rclone sync crypt-backup:/library /music/artists --progress
```

## Monitoring

### Progress Logging

```bash
rclone sync /music/artists remote:barbossa-backup/library \
  --progress \
  --stats 30s \
  --log-file /var/log/barbossa/rclone.log \
  --log-level INFO
```

### Webhook Notifications

```bash
# Using rclone's built-in RC (remote control)
rclone rcd --rc-web-gui &

# Query stats via HTTP
curl http://localhost:5572/core/stats
```

## Docker Integration

### Dockerfile Addition

```dockerfile
# Install rclone
RUN curl https://rclone.org/install.sh | bash

# Copy rclone config
COPY config/rclone.conf /root/.config/rclone/rclone.conf
```

### Docker Compose Volume

```yaml
services:
  worker:
    volumes:
      - ./config/rclone.conf:/root/.config/rclone/rclone.conf:ro
```

## Security Notes

1. **Config file permissions**: `chmod 600 ~/.config/rclone/rclone.conf`
2. **Environment variables**: Store sensitive keys in `.env`, not config
3. **Encryption**: Consider crypt remote for sensitive libraries
4. **Service accounts**: Use dedicated accounts for automated backups
5. **Token refresh**: Google Drive tokens expire; use service account for headless
