# daily_revenue_refresh.ps1
# Windows scheduled-task wrapper. Runs every morning to:
#   1. Scrape POVR + VRPorn daily totals (~30 sec)
#   2. Push them into the Premium Breakdowns sheet's _DailyData tab
#
# Logs land in Dropbox so we can inspect from any machine without SSH.
# SLR is intentionally NOT scraped here -- it's reCAPTCHA-gated and would
# fail every run; it'll join once we have API access or a 2Captcha key.

$ErrorActionPreference = "Continue"

$RepoDir   = "C:\Users\andre\eclatech-hub"
$LogDir    = "C:\Users\andre\Dropbox\AudioTraining"
$LogFile   = Join-Path $LogDir "revenue_refresh.log"

function Log {
    param([string]$Message)
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue
}

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Log "================================================="
Log "Daily revenue refresh starting"
Log "Repo: $RepoDir"

Set-Location $RepoDir

# 1. Scrape -- daily-only mode. ~10s POVR + ~5s VRPorn.
Log "Step 1/2: scraping daily totals..."
$scrapeOutput = & py "$RepoDir\scrape_revenue_data.py" --daily 2>&1 | Out-String
Log $scrapeOutput
if ($LASTEXITCODE -ne 0) {
    Log "WARN: scrape exited with code $LASTEXITCODE -- continuing to upload"
}

# 2. Upload -- auto-discovers ~/Documents/povr_daily.csv and vrporn_daily.csv.
#    Idempotent upsert by (date, platform, studio) so re-running mid-day is safe.
Log "Step 2/2: pushing to Premium Breakdowns sheet..."
$uploadOutput = & py "$RepoDir\refresh_premium_breakdowns.py" 2>&1 | Out-String
Log $uploadOutput
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: upload exited with code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Log "Daily revenue refresh complete."
Log "================================================="
