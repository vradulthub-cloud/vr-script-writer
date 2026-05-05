# daily_revenue_refresh.ps1
# Windows scheduled-task wrapper. Runs every morning to:
#   1. Scrape POVR + VRPorn + SLR daily totals (~60 sec total)
#   2. Push them into the Premium Breakdowns sheet's _DailyData tab
#
# Logs land in Dropbox so we can inspect from any machine without SSH.
# SLR cookie staleness is checked at the top of the run -- if cookies are
# 25+ days old, a loud ATTENTION line is written to the log so the user
# sees it next time they open Dropbox.

$ErrorActionPreference = "Continue"

$RepoDir       = "C:\Users\andre\eclatech-hub"
$LogDir        = "C:\Users\andre\Dropbox\AudioTraining"
$LogFile       = Join-Path $LogDir "revenue_refresh.log"
$SlrCookieFile = "C:\Users\andre\.scraper_state\slr.json"
$AttentionFile = Join-Path $LogDir "REVENUE_NEEDS_ATTENTION.txt"

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

# Cookie-age check: SLR cookies last ~30 days. Warn at 25 to give the user
# a few days of runway before the daily SLR scrape starts failing.
if (Test-Path $SlrCookieFile) {
    $cookieAge = (Get-Date) - (Get-Item $SlrCookieFile).LastWriteTime
    $ageDays = [math]::Round($cookieAge.TotalDays, 1)
    Log ("SLR cookie age: {0} days" -f $ageDays)
    if ($ageDays -ge 25) {
        Log "**********************************************"
        Log "ATTENTION: SLR cookies are $ageDays days old."
        Log "ACTION: Run on your Mac:"
        Log "  python3 /Users/andrewninn/Scripts/slr_refresh_cookies.py"
        Log "If skipped, SLR refresh will start failing in ~5 days."
        Log "**********************************************"
        # Drop a tiny flag file in Dropbox so the user notices it on their desktop.
        # Replaced (not appended) each run so the date inside is always current.
        $flagBody = "SLR cookies are $ageDays days old.`r`n`r`nRun on your Mac:`r`n  python3 /Users/andrewninn/Scripts/slr_refresh_cookies.py`r`n`r`n(File auto-removed when cookies are refreshed.)`r`n"
        Set-Content -Path $AttentionFile -Value $flagBody -ErrorAction SilentlyContinue
    } else {
        # Cookies are fresh -- clear any leftover attention flag.
        if (Test-Path $AttentionFile) {
            Remove-Item $AttentionFile -ErrorAction SilentlyContinue
        }
    }
} else {
    Log "WARN: SLR cookie file not found at $SlrCookieFile (run slr_refresh_cookies.py from Mac)"
}

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
