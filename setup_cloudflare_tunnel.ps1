# setup_cloudflare_tunnel.ps1
# Run ONCE on Windows to install cloudflared and create a persistent tunnel
# for the FastAPI backend (port 8502).
#
# After running:
#   1. The tunnel URL is printed — copy it
#   2. Update NEXT_PUBLIC_API_URL on Vercel to that URL
#   3. Add the URL to CORS origins in api/main.py and redeploy

$ErrorActionPreference = "Stop"

$WINGET = "winget"
$CLOUDFLARED = "C:\Program Files\cloudflared\cloudflared.exe"
$SERVICE_NAME = "EclatechHubTunnel"

# ── 1. Install cloudflared ─────────────────────────────────────────────────────
Write-Host "`n[1/4] Installing cloudflared..." -ForegroundColor Cyan

& $WINGET install --id Cloudflare.cloudflared --silent --accept-source-agreements --accept-package-agreements
if (-not (Test-Path $CLOUDFLARED)) {
    # Try alternate install path
    $CLOUDFLARED = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
}
if (-not $CLOUDFLARED -or -not (Test-Path $CLOUDFLARED)) {
    Write-Error "cloudflared not found after install. Try: winget install Cloudflare.cloudflared"
    exit 1
}
Write-Host "  cloudflared installed: $CLOUDFLARED" -ForegroundColor Green

# ── 2. Create a quick tunnel (no login needed — generates *.trycloudflare.com) ─
# NOTE: trycloudflare.com tunnels are ephemeral (restart = new URL).
# For a STABLE URL: run `cloudflared login` to connect your CF account,
# then replace this section with `cloudflared tunnel create eclatech-api`
Write-Host "`n[2/4] Starting quick tunnel on port 8502..." -ForegroundColor Cyan
Write-Host "  (This is a temporary trycloudflare.com URL — see below for permanent option)"

# Run tunnel in background just long enough to print URL, then we set up a service
$proc = Start-Process -FilePath $CLOUDFLARED `
    -ArgumentList "tunnel", "--url", "http://localhost:8502" `
    -RedirectStandardError "$env:TEMP\cf_tunnel_stderr.txt" `
    -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 6
$tunnelLog = Get-Content "$env:TEMP\cf_tunnel_stderr.txt" -ErrorAction SilentlyContinue
$tunnelUrl = ($tunnelLog | Select-String "https://.*\.trycloudflare\.com") -replace ".*?(https://\S+trycloudflare\.com).*", '$1'

if ($tunnelUrl) {
    Write-Host "`n  Tunnel URL: $tunnelUrl" -ForegroundColor Yellow
    Write-Host "  (Save this — you'll need it for Vercel env vars)"
} else {
    Write-Host "  Could not auto-detect URL. Check: $env:TEMP\cf_tunnel_stderr.txt"
    Write-Host "  Run manually: cloudflared tunnel --url http://localhost:8502"
}

# Stop temp process — service will take over
Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue

# ── 3. Install as NSSM service ────────────────────────────────────────────────
Write-Host "`n[3/4] Installing as NSSM service ($SERVICE_NAME)..." -ForegroundColor Cyan
$NSSM = "C:\Users\andre\nssm\nssm-2.24\win32\nssm.exe"

& $NSSM install $SERVICE_NAME $CLOUDFLARED "tunnel --url http://localhost:8502"
& $NSSM set $SERVICE_NAME AppStdout "$env:TEMP\cf_tunnel_stdout.log"
& $NSSM set $SERVICE_NAME AppStderr "$env:TEMP\cf_tunnel_stderr_svc.log"
& $NSSM set $SERVICE_NAME Start SERVICE_AUTO_START

net start $SERVICE_NAME
Write-Host "  $SERVICE_NAME service started." -ForegroundColor Green

# ── 4. Print the URL from the service log ─────────────────────────────────────
Write-Host "`n[4/4] Waiting for tunnel URL from service..." -ForegroundColor Cyan
Start-Sleep -Seconds 8
$svcLog = Get-Content "$env:TEMP\cf_tunnel_stderr_svc.log" -ErrorAction SilentlyContinue
$svcUrl = ($svcLog | Select-String "https://.*\.trycloudflare\.com") -replace ".*?(https://\S+trycloudflare\.com).*", '$1'

Write-Host "`n=== IMPORTANT ===" -ForegroundColor Yellow
if ($svcUrl) {
    Write-Host "  Tunnel URL: $svcUrl" -ForegroundColor Green
} else {
    Write-Host "  URL not captured yet. Run this to get it:" -ForegroundColor Yellow
    Write-Host "  Get-Content '$env:TEMP\cf_tunnel_stderr_svc.log' | Select-String 'trycloudflare'"
}

Write-Host "`n  Next steps:"
Write-Host "  1. Copy the *.trycloudflare.com URL above"
Write-Host "  2. On Vercel dashboard: Settings > Environment Variables"
Write-Host "     Set NEXT_PUBLIC_API_URL = <tunnel URL>"
Write-Host "  3. Redeploy Next.js on Vercel"
Write-Host ""
Write-Host "  NOTE: trycloudflare.com URL changes on service restart."
Write-Host "  For a STABLE URL, register a free domain and use Cloudflare Tunnel with your account."
Write-Host "  (Cheapest: Cloudflare Registrar — .com ~$10/yr, often find cheap alternatives)"
