#!/bin/bash
# deploy_nextjs.sh — Build Next.js on Mac, deploy standalone bundle to Windows
#
# Usage:
#   ./deploy_nextjs.sh
#
# Requires hub/.env.production to exist (copy from hub/.env.local.example and fill in)

set -euo pipefail

WINDOWS_HOST="andre@100.90.90.68"
SSH_KEY="$HOME/.ssh/id_ed25519_win"
WIN_PATH="C:/Users/andre/eclatech-hub-next"
HUB_DIR="$(cd "$(dirname "$0")/hub" && pwd)"

echo "=== Eclatech Hub — Next.js Deploy ==="
echo "Building in: $HUB_DIR"

# ── 1. Build ──────────────────────────────────────────────────────────────────
cd "$HUB_DIR"
echo ""
echo "[1/4] Building Next.js (standalone)..."
npm run build

# ── 2. Assemble standalone bundle ────────────────────────────────────────────
echo ""
echo "[2/4] Assembling standalone bundle..."
STANDALONE="$HUB_DIR/.next/standalone"

# Next.js standalone needs static + public copied alongside server.js
cp -r "$HUB_DIR/.next/static"  "$STANDALONE/.next/static"
cp -r "$HUB_DIR/public"        "$STANDALONE/public"

echo "      Bundle size: $(du -sh "$STANDALONE" | cut -f1)"

# ── 3. SCP to Windows ────────────────────────────────────────────────────────
echo ""
echo "[3/4] Uploading to Windows ($WIN_PATH)..."

# Create the target directory on Windows
ssh -i "$SSH_KEY" "$WINDOWS_HOST" \
  "powershell -Command \"New-Item -ItemType Directory -Force -Path '$WIN_PATH' | Out-Null\""

# Upload — rsync would be nicer but SCP works everywhere
scp -i "$SSH_KEY" -r "$STANDALONE/." "$WINDOWS_HOST:$WIN_PATH/"

echo "      Upload complete."

# ── 4. Restart service ───────────────────────────────────────────────────────
echo ""
echo "[4/4] Restarting EclatechHubNext service..."
ssh -i "$SSH_KEY" "$WINDOWS_HOST" \
  "powershell -Command \"
    \$nssm = 'C:\\Users\\andre\\nssm\\nssm-2.24\\win32\\nssm.exe'
    \$svc  = 'EclatechHubNext'
    \$status = & \$nssm status \$svc 2>&1
    if (\$status -match 'SERVICE_RUNNING') {
      net stop \$svc
      net start \$svc
    } else {
      Write-Host 'Service not running or not found — run setup_nextjs_service.ps1 first'
    }
  \"" || echo "  (service not installed yet — run setup_nextjs_service.ps1 first)"

echo ""
echo "=== Deploy complete ==="
echo "  App: https://desktop-9d407v9.tail3f755a.ts.net:3000"
echo "  API: https://desktop-9d407v9.tail3f755a.ts.net:8502"
