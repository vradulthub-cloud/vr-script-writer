# setup_tailscale_funnel.ps1
# Run ONCE on Windows to expose FastAPI publicly via Tailscale Funnel.
#
# This makes https://desktop-9d407v9.tail3f755a.ts.net:8443 publicly accessible
# (no Tailscale required for visitors) and forwards traffic to localhost:8502.
#
# Prerequisites:
#   - Tailscale installed and logged in (it's already running)
#   - Run as Administrator

Write-Host "=== Tailscale Funnel Setup ===" -ForegroundColor Cyan
Write-Host "  Exposing FastAPI (localhost:8502) on public port 8443"
Write-Host ""

# ── 1. Configure serve: port 8443 → localhost:8502 ───────────────────────────
Write-Host "[1/2] Configuring tailscale serve..." -ForegroundColor Cyan
& tailscale serve --bg --https=8443 http://localhost:8502
Write-Host "  Serve configured." -ForegroundColor Green

# ── 2. Enable funnel on port 8443 ─────────────────────────────────────────────
Write-Host "[2/2] Enabling tailscale funnel..." -ForegroundColor Cyan
& tailscale funnel --bg 8443
Write-Host "  Funnel enabled." -ForegroundColor Green

# ── Result ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host ""
Write-Host "  FastAPI is now publicly accessible at:" -ForegroundColor Yellow
Write-Host "  https://desktop-9d407v9.tail3f755a.ts.net:8443" -ForegroundColor White
Write-Host ""
Write-Host "  Test it from any browser (no VPN needed):"
Write-Host "  https://desktop-9d407v9.tail3f755a.ts.net:8443/api/health"
Write-Host ""
Write-Host "  Current serve config:"
& tailscale serve status
