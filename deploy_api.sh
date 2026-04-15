#!/bin/bash
# deploy_api.sh — Deploy FastAPI backend to Windows
#
# Copies api/ to C:\Users\andre\eclatech-hub\api\ and (re)installs the
# EclatechHubAPI NSSM service.
#
# Usage:
#   ./deploy_api.sh

set -euo pipefail

WINDOWS_HOST="andre@100.90.90.68"
SSH_KEY="$HOME/.ssh/id_ed25519_win"
WIN_HUB="C:/Users/andre/eclatech-hub"
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Eclatech Hub — FastAPI Deploy ==="

# ── 1. SCP api/ ──────────────────────────────────────────────────────────────
echo "[1/3] Uploading api/ to Windows..."
# No trailing slash on source — copies the api/ directory itself, overwriting contents
scp -i "$SSH_KEY" -r "$SCRIPTS_DIR/api" "$WINDOWS_HOST:$WIN_HUB/"
echo "      Done."

# ── 2. Install / update Python deps ──────────────────────────────────────────
echo "[2/3] Checking Python deps..."
ssh -i "$SSH_KEY" "$WINDOWS_HOST" \
  "pip install fastapi uvicorn pydantic-settings gspread google-auth google-auth-oauthlib -q"
echo "      Deps up to date."

# ── 3. Restart / start service ───────────────────────────────────────────────
echo "[3/3] Restarting EclatechHubAPI service..."
ssh -i "$SSH_KEY" "$WINDOWS_HOST" \
  "powershell -Command \"
    \$nssm = 'C:\\Users\\andre\\nssm\\nssm-2.24\\win32\\nssm.exe'
    \$svc  = 'EclatechHubAPI'
    \$status = & \$nssm status \$svc 2>&1
    if (\$status -match 'SERVICE_RUNNING') {
      net stop \$svc
      net start \$svc
    } else {
      Write-Host 'Service not installed — run setup_windows_services.ps1 first'
    }
  \"" || echo "  (service not installed yet — run setup_windows_services.ps1 first)"

echo ""
echo "=== API deploy complete ==="
echo "  Health: http://100.90.90.68:8502/api/health"
