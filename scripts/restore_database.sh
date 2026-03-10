#!/bin/bash
# BluSuite Database Restore Script
# Restores PostgreSQL database from backup with safety checks

set -e  # Exit on error

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

BACKUP_DIR="/opt/blusuite/backups"
DB_NAME="blusuite_db"
DB_USER="blusuite_user"
LOG_FILE="${BACKUP_DIR}/restore.log"

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

list_backups() {
    echo ""
    echo "Available backups:"
    echo "─────────────────────────────────────────────────────────────"
    find "$BACKUP_DIR" -name "blusuite_*.sql.gz" -type f -printf "%T@ %p\n" | \
        sort -rn | \
        awk '{print NR". "$2" ("strftime("%Y-%m-%d %H:%M:%S", $1)")"}' | \
        head -20
    echo "─────────────────────────────────────────────────────────────"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Main Script
# ─────────────────────────────────────────────────────────────────────────────

log "=== BluSuite Database Restore Started ==="

# Check if backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
    error "Backup directory does not exist: $BACKUP_DIR"
fi

# List available backups
list_backups

# Get backup file from argument or prompt
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 /opt/blusuite/backups/blusuite_20260310_020000.sql.gz"
    echo ""
    echo "Or select a backup number from the list above:"
    read -p "Enter backup number (or full path): " BACKUP_INPUT
    
    if [[ "$BACKUP_INPUT" =~ ^[0-9]+$ ]]; then
        # User entered a number
        BACKUP_FILE=$(find "$BACKUP_DIR" -name "blusuite_*.sql.gz" -type f -printf "%T@ %p\n" | \
            sort -rn | \
            awk -v num="$BACKUP_INPUT" 'NR==num {print $2}')
        
        if [ -z "$BACKUP_FILE" ]; then
            error "Invalid backup number"
        fi
    else
        # User entered a path
        BACKUP_FILE="$BACKUP_INPUT"
    fi
else
    BACKUP_FILE="$1"
fi

# Verify backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    error "Backup file not found: $BACKUP_FILE"
fi

log "Selected backup: $BACKUP_FILE"

# Verify backup integrity
log "Verifying backup integrity..."
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    error "Backup file is corrupted"
fi
log "Backup integrity verified"

# ─────────────────────────────────────────────────────────────────────────────
# Safety Confirmation
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo "⚠️  WARNING: This will REPLACE the current database with the backup!"
echo "Database: $DB_NAME"
echo "Backup: $BACKUP_FILE"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log "Restore cancelled by user"
    exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
# Pre-Restore Backup
# ─────────────────────────────────────────────────────────────────────────────

log "Creating safety backup of current database..."
SAFETY_BACKUP="${BACKUP_DIR}/pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"

if pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$SAFETY_BACKUP"; then
    log "Safety backup created: $SAFETY_BACKUP"
else
    error "Failed to create safety backup"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Stop Application
# ─────────────────────────────────────────────────────────────────────────────

log "Stopping BluSuite application..."
if systemctl is-active --quiet blusuite; then
    systemctl stop blusuite
    log "Application stopped"
else
    log "Application was not running"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Database Restore
# ─────────────────────────────────────────────────────────────────────────────

log "Dropping existing database..."
if dropdb -U "$DB_USER" "$DB_NAME" 2>/dev/null; then
    log "Database dropped"
else
    log "WARNING: Could not drop database (may not exist)"
fi

log "Creating fresh database..."
if createdb -U "$DB_USER" "$DB_NAME"; then
    log "Database created"
else
    error "Failed to create database"
fi

log "Restoring database from backup..."
if zcat "$BACKUP_FILE" | psql -U "$DB_USER" "$DB_NAME" > /dev/null 2>&1; then
    log "Database restored successfully"
else
    error "Database restore failed - attempting to restore safety backup"
    zcat "$SAFETY_BACKUP" | psql -U "$DB_USER" "$DB_NAME"
    error "Restored to safety backup. Original restore failed."
fi

# ─────────────────────────────────────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────────────────────────────────────

log "Verifying restored database..."

# Count tables
TABLE_COUNT=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'" | xargs)

if [ "$TABLE_COUNT" -lt 10 ]; then
    error "Restored database has only $TABLE_COUNT tables (expected 20+)"
fi

log "Restored database contains $TABLE_COUNT tables"

# ─────────────────────────────────────────────────────────────────────────────
# Restart Application
# ─────────────────────────────────────────────────────────────────────────────

log "Starting BluSuite application..."
if systemctl start blusuite; then
    log "Application started"
    sleep 3
    
    if systemctl is-active --quiet blusuite; then
        log "Application is running"
    else
        error "Application failed to start"
    fi
else
    error "Failed to start application"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

log "=== Restore Summary ==="
log "Restored from: $BACKUP_FILE"
log "Tables restored: $TABLE_COUNT"
log "Safety backup: $SAFETY_BACKUP"
log "=== Restore Completed Successfully ==="

echo ""
echo "✅ Database restored successfully!"
echo "Safety backup saved at: $SAFETY_BACKUP"
echo ""

exit 0
