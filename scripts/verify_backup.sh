#!/bin/bash
# BluSuite Backup Verification Script
# Tests backup integrity and restoration capability

set -e

BACKUP_DIR="/opt/blusuite/backups"
TEST_DB="blusuite_test_restore"
DB_USER="blusuite_user"
LOG_FILE="${BACKUP_DIR}/verify.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $1"
    exit 1
}

log "=== Backup Verification Started ==="

# Get latest backup
LATEST_BACKUP=$(find "$BACKUP_DIR" -name "blusuite_*.sql.gz" -type f -printf "%T@ %p\n" | sort -rn | head -1 | awk '{print $2}')

if [ -z "$LATEST_BACKUP" ]; then
    error "No backups found in $BACKUP_DIR"
fi

log "Testing backup: $LATEST_BACKUP"

# Verify file integrity
log "Checking file integrity..."
if ! gzip -t "$LATEST_BACKUP" 2>/dev/null; then
    error "Backup file is corrupted"
fi
log "✓ File integrity OK"

# Test restoration to temporary database
log "Creating test database..."
dropdb -U "$DB_USER" "$TEST_DB" 2>/dev/null || true
createdb -U "$DB_USER" "$TEST_DB"

log "Restoring to test database..."
if zcat "$LATEST_BACKUP" | psql -U "$DB_USER" "$TEST_DB" > /dev/null 2>&1; then
    log "✓ Restore successful"
else
    error "Restore failed"
fi

# Verify table count
TABLE_COUNT=$(psql -U "$DB_USER" -d "$TEST_DB" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'" | xargs)
log "✓ Tables restored: $TABLE_COUNT"

# Verify key tables exist
CRITICAL_TABLES=("auth_user" "accounts_company" "payroll_payroll" "blu_core_auditlog")
for table in "${CRITICAL_TABLES[@]}"; do
    if psql -U "$DB_USER" -d "$TEST_DB" -t -c "SELECT 1 FROM information_schema.tables WHERE table_name = '$table'" | grep -q 1; then
        log "✓ Critical table exists: $table"
    else
        log "⚠ WARNING: Critical table missing: $table"
    fi
done

# Cleanup
log "Cleaning up test database..."
dropdb -U "$DB_USER" "$TEST_DB"

log "=== Verification Completed Successfully ==="
echo "✅ Latest backup is valid and restorable"
exit 0
