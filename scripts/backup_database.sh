#!/bin/bash
# BluSuite Database Backup Script
# Performs PostgreSQL backup with compression, retention policy, and verification

set -e  # Exit on error

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

BACKUP_DIR="/opt/blusuite/backups"
BACKUP_RETENTION_DAYS=30
DB_NAME="blusuite_db"
DB_USER="blusuite_user"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/blusuite_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Remote backup (optional - configure for production)
REMOTE_BACKUP_ENABLED=false
REMOTE_BACKUP_HOST=""
REMOTE_BACKUP_PATH=""

# ─────────────────────────────────────────────────────────────────────────────
# Functions
# ─────────────────────────────────────────────────────────────────────────────

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $1"
    exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# Pre-flight Checks
# ─────────────────────────────────────────────────────────────────────────────

log "=== BluSuite Database Backup Started ==="

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Check disk space (require at least 1GB free)
AVAILABLE_SPACE=$(df -BG "$BACKUP_DIR" | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 1 ]; then
    error "Insufficient disk space. Available: ${AVAILABLE_SPACE}GB, Required: 1GB"
fi

log "Disk space check passed: ${AVAILABLE_SPACE}GB available"

# ─────────────────────────────────────────────────────────────────────────────
# Database Backup
# ─────────────────────────────────────────────────────────────────────────────

log "Starting database dump: $DB_NAME"

# Perform backup with compression
if pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup completed successfully: $BACKUP_FILE ($BACKUP_SIZE)"
else
    error "Database backup failed"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Backup Verification
# ─────────────────────────────────────────────────────────────────────────────

log "Verifying backup integrity..."

# Check if file exists and is not empty
if [ ! -s "$BACKUP_FILE" ]; then
    error "Backup file is empty or does not exist"
fi

# Verify gzip integrity
if gzip -t "$BACKUP_FILE" 2>/dev/null; then
    log "Backup integrity verified"
else
    error "Backup file is corrupted"
fi

# Count tables in backup (basic sanity check)
TABLE_COUNT=$(zcat "$BACKUP_FILE" | grep -c "CREATE TABLE" || true)
if [ "$TABLE_COUNT" -lt 10 ]; then
    log "WARNING: Only $TABLE_COUNT tables found in backup (expected 20+)"
else
    log "Backup contains $TABLE_COUNT tables"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Remote Backup (Optional)
# ─────────────────────────────────────────────────────────────────────────────

if [ "$REMOTE_BACKUP_ENABLED" = true ]; then
    log "Uploading backup to remote storage..."
    
    if scp "$BACKUP_FILE" "${REMOTE_BACKUP_HOST}:${REMOTE_BACKUP_PATH}/"; then
        log "Remote backup uploaded successfully"
    else
        log "WARNING: Remote backup upload failed (local backup still available)"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Cleanup Old Backups
# ─────────────────────────────────────────────────────────────────────────────

log "Cleaning up backups older than $BACKUP_RETENTION_DAYS days..."

DELETED_COUNT=$(find "$BACKUP_DIR" -name "blusuite_*.sql.gz" -type f -mtime +$BACKUP_RETENTION_DAYS -delete -print | wc -l)

if [ "$DELETED_COUNT" -gt 0 ]; then
    log "Deleted $DELETED_COUNT old backup(s)"
else
    log "No old backups to delete"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Backup Summary
# ─────────────────────────────────────────────────────────────────────────────

TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "blusuite_*.sql.gz" -type f | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

log "=== Backup Summary ==="
log "Latest backup: $BACKUP_FILE"
log "Backup size: $BACKUP_SIZE"
log "Total backups: $TOTAL_BACKUPS"
log "Total storage used: $TOTAL_SIZE"
log "=== Backup Completed Successfully ==="

exit 0
