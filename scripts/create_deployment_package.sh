#!/bin/bash
# ============================================================
# BLU Suite - Local Deployment Package Creator (Linux/Mac)
# ============================================================
# This script creates a deployment-ready archive from your local machine
# Usage: ./scripts/create_deployment_package.sh

set -e

echo "========================================"
echo "BLU Suite - Deployment Package Creator"
echo "========================================"
echo ""

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Set deployment package name with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="blusuite_deploy_$TIMESTAMP"
TEMP_DIR="/tmp/$PACKAGE_NAME"
OUTPUT_FILE="$PROJECT_ROOT/$PACKAGE_NAME.tar.gz"

echo "Project Root: $PROJECT_ROOT"
echo "Package Name: $PACKAGE_NAME"
echo ""

# Create temporary directory
echo "[1/5] Creating temporary directory..."
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Files and directories to include
INCLUDE_ITEMS=(
    "ems_project"
    "blu_analytics"
    "blu_assets"
    "blu_billing"
    "blu_core"
    "blu_projects"
    "blu_staff"
    "blu_support"
    "tenant_management"
    "shared_core"
    "ems_app"
    "future_modules"
    "static"
    "nginx"
    "scripts"
    "manage.py"
    "requirements.txt"
    "requirements-deploy.txt"
    "gunicorn.conf.py"
    "blusuite.service"
    ".env.production.example"
    ".dockerignore"
    "postcss.config.js"
    "package.json"
    "package-lock.json"
)

# Copy files to temp directory
echo "[2/5] Copying project files..."
COPIED_COUNT=0
for ITEM in "${INCLUDE_ITEMS[@]}"; do
    SOURCE_PATH="$PROJECT_ROOT/$ITEM"
    if [ -e "$SOURCE_PATH" ]; then
        cp -r "$SOURCE_PATH" "$TEMP_DIR/"
        echo "  ✓ Copied: $ITEM"
        ((COPIED_COUNT++))
    else
        echo "  ⚠ Skipped (not found): $ITEM"
    fi
done
echo "  Total items copied: $COPIED_COUNT"
echo ""

# Clean up Python cache and unnecessary files
echo "[3/5] Cleaning up unnecessary files..."
find "$TEMP_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$TEMP_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$TEMP_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
find "$TEMP_DIR" -type f -name "*.pyd" -delete 2>/dev/null || true
find "$TEMP_DIR" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find "$TEMP_DIR" -type f -name "*.log" -delete 2>/dev/null || true
echo "  ✓ Cleanup completed"
echo ""

# Create deployment info file
echo "[4/5] Creating deployment info..."
cat > "$TEMP_DIR/DEPLOYMENT_INFO.txt" << EOF
BLU Suite Deployment Package
=============================
Created: $(date '+%Y-%m-%d %H:%M:%S')
Source: Local Machine
Package: $PACKAGE_NAME

DEPLOYMENT INSTRUCTIONS:
1. Upload this package to your server
2. Extract: tar -xzf $PACKAGE_NAME.tar.gz
3. Follow DEPLOYMENT_FROM_LOCAL.md instructions

For support, check the deployment documentation.
EOF
echo "  ✓ Deployment info created"
echo ""

# Create tar.gz archive
echo "[5/5] Creating deployment archive..."
cd /tmp
tar -czf "$OUTPUT_FILE" "$PACKAGE_NAME"
cd - > /dev/null

# Cleanup temp directory
rm -rf "$TEMP_DIR"

# Display results
echo ""
echo "========================================"
echo "✓ DEPLOYMENT PACKAGE CREATED"
echo "========================================"
echo ""
echo "Package Location:"
echo "  $OUTPUT_FILE"
echo ""
FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
echo "Package Size: $FILE_SIZE"
echo ""
echo "Next Steps:"
echo "  1. Upload package to your server using SCP:"
echo "     scp $OUTPUT_FILE root@YOUR_SERVER_IP:/tmp/"
echo ""
echo "  2. SSH into your server and extract:"
echo "     ssh root@YOUR_SERVER_IP"
echo "     cd /opt/blusuite"
echo "     tar -xzf /tmp/$PACKAGE_NAME.tar.gz --strip-components=1"
echo ""
echo "  3. Follow the deployment guide in DEPLOYMENT_FROM_LOCAL.md"
echo ""
