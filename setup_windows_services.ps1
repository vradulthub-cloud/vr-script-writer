# setup_windows_services.ps1
# Run this ONCE on the Windows machine to create the two new NSSM services.
# The api/ dir and eclatech-hub-next/ dir must already be deployed (run deploy scripts first).
#
# TODO: Fill in the two Google OAuth values below before running.

$NSSM    = "C:\Users\andre\nssm\nssm-2.24\win32\nssm.exe"
$PYTHON  = "C:\Program Files\Python311\python.exe"
$NODE    = "C:\Program Files\nodejs\node.exe"
$HUB_DIR = "C:\Users\andre\eclatech-hub"
$NEXT_DIR = "C:\Users\andre\eclatech-hub-next"

# ── TODO: paste these from Google Cloud Console ───────────────────────────────
$GOOGLE_CLIENT_ID     = "TODO"
$GOOGLE_CLIENT_SECRET = "TODO"
# ─────────────────────────────────────────────────────────────────────────────

# Pre-generated — do not change
$AUTH_SECRET = "N/+Hix+++b0tVo9Rh/ChTCQqtnzAxVhJX0wZYpxVsco="

# Pull ANTHROPIC_API_KEY from the existing Streamlit service
$rawEnv = & $NSSM get EclatechHub AppEnvironmentExtra 2>&1
$ANTHROPIC_API_KEY = ($rawEnv -split "`0" | Where-Object { $_ -match "^ANTHROPIC_API_KEY=" }) -replace "ANTHROPIC_API_KEY=", ""

if (-not $ANTHROPIC_API_KEY) {
    Write-Warning "Could not read ANTHROPIC_API_KEY from EclatechHub service — set it manually"
    $ANTHROPIC_API_KEY = ""
}

if ($GOOGLE_CLIENT_ID -eq "TODO") {
    Write-Error "Fill in GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET before running this script."
    exit 1
}

# ── 1. FastAPI — EclatechHubAPI (port 8502) ──────────────────────────────────
Write-Host "`n[1/2] Setting up EclatechHubAPI..." -ForegroundColor Cyan

& $NSSM install EclatechHubAPI $PYTHON "-m uvicorn api.main:app --host 0.0.0.0 --port 8502"
& $NSSM set EclatechHubAPI AppDirectory    $HUB_DIR
& $NSSM set EclatechHubAPI AppStdout       "$HUB_DIR\nssm_api_stdout.log"
& $NSSM set EclatechHubAPI AppStderr       "$HUB_DIR\nssm_api_stderr.log"
& $NSSM set EclatechHubAPI AppRotateFiles  1
& $NSSM set EclatechHubAPI Start           SERVICE_AUTO_START
& $NSSM set EclatechHubAPI AppEnvironmentExtra "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY`0GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID"

net start EclatechHubAPI
Write-Host "  EclatechHubAPI started on :8502" -ForegroundColor Green

# ── 2. Next.js — EclatechHubNext (port 3000) ─────────────────────────────────
Write-Host "`n[2/2] Setting up EclatechHubNext..." -ForegroundColor Cyan

& $NSSM install EclatechHubNext $NODE "server.js"
& $NSSM set EclatechHubNext AppDirectory    $NEXT_DIR
& $NSSM set EclatechHubNext AppStdout       "$NEXT_DIR\nssm_next_stdout.log"
& $NSSM set EclatechHubNext AppStderr       "$NEXT_DIR\nssm_next_stderr.log"
& $NSSM set EclatechHubNext AppRotateFiles  1
& $NSSM set EclatechHubNext Start           SERVICE_AUTO_START
& $NSSM set EclatechHubNext AppEnvironmentExtra "PORT=3000`0HOSTNAME=0.0.0.0`0NODE_ENV=production`0AUTH_SECRET=$AUTH_SECRET`0GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID`0GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET`0NEXT_PUBLIC_API_URL=http://localhost:8502"

net start EclatechHubNext
Write-Host "  EclatechHubNext started on :3000" -ForegroundColor Green

Write-Host "`n=== Done ===" -ForegroundColor Green
Write-Host "  App:      https://desktop-9d407v9.tail3f755a.ts.net:3000"
Write-Host "  API:      http://100.90.90.68:8502/api/health"
Write-Host "  Streamlit: https://desktop-9d407v9.tail3f755a.ts.net (8501)"
