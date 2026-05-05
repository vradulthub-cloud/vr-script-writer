# Revenue refresh — setup notes

The Revenue dashboard (`/admin/revenue`) is fed by the **Premium Breakdowns** Google Sheet, which is refreshed daily by a Windows scheduled task that scrapes each partner portal.

## Daily refresh — what runs every morning at 6 AM

`EclatechRevenueDailyRefresh` (Windows Task Scheduler) runs `daily_revenue_refresh.ps1`, which calls:

1. **`scrape_revenue_data.py --daily`** — pulls fresh daily totals
2. **`refresh_premium_breakdowns.py`** — pushes them into the sheet's `_DailyData` tab

Per-platform status:

| Platform | Mode | Notes |
|---|---|---|
| **POVR** | `--povr-daily` | 60-day window, ~10s, fully unattended |
| **VRPorn** | `--vrporn` | 20-day window, ~5s, fully unattended |
| **SLR** | `--slr` | Daily window, requires `TWOCAPTCHA_API_KEY` (see below) |

Logs land at `~/Dropbox/AudioTraining/revenue_refresh.log` so you can read them from any machine.

## Enabling SLR (one-time setup)

SLR's login is gated by Google reCAPTCHA v2. To run unattended, we use 2Captcha to solve the challenge automatically.

### Steps:

1. **Create a 2Captcha account** at <https://2captcha.com>. Sign up, verify email.
2. **Add funds** — minimum $1, recommended $5. SLR daily refresh = ~365 solves/year × $0.003 = ~$1.10/year of captcha budget. Funding $5 covers ~4 years.
3. **Copy your API key** from <https://2captcha.com/enterpage> (top of page, under your account name).
4. **Add it to Windows `.env`**:
   ```
   TWOCAPTCHA_API_KEY=your_key_here
   ```
   File location: `C:\Users\andre\eclatech-hub\.env`
5. **Test it once manually** to confirm:
   ```
   ssh -i ~/.ssh/id_ed25519_win andre@100.90.90.68
   cd C:\Users\andre\eclatech-hub
   py scrape_revenue_data.py --slr
   ```
   First run takes ~30s (login + captcha solve + page navigation). Subsequent runs reuse cookies (`~/.scraper_state/slr.json`) until they expire.

After step 5 succeeds the daily scheduled task will automatically include SLR in its run.

## If you ever want to disable SLR

Remove `TWOCAPTCHA_API_KEY` from `.env`. The daily task will silently skip SLR; POVR + VRPorn keep running.

## Manual one-off commands

```sh
# Just refresh today's totals (POVR + VRPorn, no SLR)
py scrape_revenue_data.py --daily

# Full POVR per-video re-scrape (slow, ~3 min, only run when catalog changed)
py scrape_revenue_data.py --povr

# SLR with --headed for first-time interactive login (no 2Captcha needed if you'll click "I'm not a robot" yourself)
py scrape_revenue_data.py --slr --headed

# Push whatever CSVs are in ~/Documents to the sheet
py refresh_premium_breakdowns.py
```

## Bust the dashboard cache after a refresh

Default cache TTL is 15 min. To force-refresh immediately:

```
GET https://desktop-9d407v9.tail3f755a.ts.net:8443/api/revenue/dashboard?refresh=true
```

(Visit `/admin/revenue?refresh=true` while logged in.)
