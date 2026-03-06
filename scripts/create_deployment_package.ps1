# ============================================================
# BLU Suite - Local Deployment Package Creator (Windows)
# ============================================================
# This script creates a deployment-ready archive from your local machine
# Usage: .\scripts\create_deployment_package.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "BLU Suite - Deployment Package Creator" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Set deployment package name with timestamp
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$PackageName = "blusuite_deploy_$Timestamp"
$TempDir = Join-Path $env:TEMP $PackageName
$OutputFile = Join-Path $ProjectRoot "$PackageName.tar.gz"

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Yellow
Write-Host "Package Name: $PackageName" -ForegroundColor Yellow
Write-Host ""

# Create temporary directory
Write-Host "[1/5] Creating temporary directory..." -ForegroundColor Green
if (Test-Path $TempDir) {
    Remove-Item -Path $TempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $TempDir | Out-Null

# Files and directories to include
$IncludeItems = @(
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
Write-Host "[2/5] Copying project files..." -ForegroundColor Green
$CopiedCount = 0
foreach ($Item in $IncludeItems) {
    $SourcePath = Join-Path $ProjectRoot $Item
    if (Test-Path $SourcePath) {
        $DestPath = Join-Path $TempDir $Item
        Copy-Item -Path $SourcePath -Destination $DestPath -Recurse -Force
        $CopiedCount++
        Write-Host "  Copied: $Item" -ForegroundColor Gray
    } else {
        Write-Host "  Skipped (not found): $Item" -ForegroundColor DarkYellow
    }
}
Write-Host "  Total items copied: $CopiedCount" -ForegroundColor Cyan
Write-Host ""

# Clean up Python cache and unnecessary files
Write-Host "[3/5] Cleaning up unnecessary files..." -ForegroundColor Green
$CleanupPatterns = @(
    "__pycache__"
    "*.pyc"
    "*.pyo"
    "*.pyd"
    ".pytest_cache"
    "*.log"
)

foreach ($Pattern in $CleanupPatterns) {
    Get-ChildItem -Path $TempDir -Filter $Pattern -Recurse -Force -ErrorAction SilentlyContinue | 
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "  Cleanup completed" -ForegroundColor Gray
Write-Host ""

# Create deployment info file
Write-Host "[4/5] Creating deployment info..." -ForegroundColor Green
$DeployInfo = @"
BLU Suite Deployment Package
=============================
Created: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Source: Local Machine
Package: $PackageName

DEPLOYMENT INSTRUCTIONS:
1. Upload this package to your server
2. Extract: tar -xzf $PackageName.tar.gz
3. Follow DEPLOYMENT_FROM_LOCAL.md instructions

For support, check the deployment documentation.
"@

$DeployInfo | Out-File -FilePath (Join-Path $TempDir "DEPLOYMENT_INFO.txt") -Encoding UTF8
Write-Host "  Deployment info created" -ForegroundColor Gray
Write-Host ""

# Create tar.gz archive using tar (if available) or 7-Zip
Write-Host "[5/5] Creating deployment archive..." -ForegroundColor Green

# Check if tar is available (Windows 10+ has built-in tar)
$TarAvailable = Get-Command tar -ErrorAction SilentlyContinue

if ($TarAvailable) {
    Write-Host "  Using built-in tar..." -ForegroundColor Gray
    Push-Location $env:TEMP
    & tar -czf $OutputFile -C $env:TEMP $PackageName
    Pop-Location
    
    if (Test-Path $OutputFile) {
        Write-Host "  Archive created successfully" -ForegroundColor Gray
    } else {
        Write-Host "  Failed to create archive" -ForegroundColor Red
        exit 1
    }
} else {
    # Fallback to creating a zip file
    Write-Host "  tar not available, creating ZIP archive instead..." -ForegroundColor Yellow
    $OutputFile = Join-Path $ProjectRoot "$PackageName.zip"
    Compress-Archive -Path $TempDir -DestinationPath $OutputFile -Force
    Write-Host "  ZIP archive created" -ForegroundColor Gray
}

# Cleanup temp directory
Remove-Item -Path $TempDir -Recurse -Force

# Display results
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "DEPLOYMENT PACKAGE CREATED" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Package Location:" -ForegroundColor Cyan
Write-Host "  $OutputFile" -ForegroundColor White
Write-Host ""
$FileSize = (Get-Item $OutputFile).Length / 1MB
Write-Host "Package Size: $([math]::Round($FileSize, 2)) MB" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Upload package to your server using SCP:" -ForegroundColor White
Write-Host "     scp $OutputFile root@YOUR_SERVER_IP:/tmp/" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. SSH into your server and extract:" -ForegroundColor White
Write-Host "     ssh root@YOUR_SERVER_IP" -ForegroundColor Gray
Write-Host "     cd /opt/blusuite" -ForegroundColor Gray
Write-Host "     tar -xzf /tmp/$PackageName.tar.gz --strip-components=1" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Follow the deployment guide in DEPLOYMENT_FROM_LOCAL.md" -ForegroundColor White
Write-Host ""
