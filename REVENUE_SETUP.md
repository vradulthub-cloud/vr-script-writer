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

## Enabling SLR — pick one path

SLR's login is gated by Google reCAPTCHA v2. The cheapest reliable path is the **30-day cookie pattern** (free + ~30 sec of clicks once a month). The fully-unattended path is **2Captcha** (~$1/year).

### Path A: Free 30-day cookie refresh (recommended)

Real Chrome with your real session almost never sees the reCAPTCHA challenge. So we let *you* log in once a month from your normal browser, capture the resulting cookies, and the daily Windows scheduled task uses them for the next ~30 days.

```sh
python3 /Users/andrewninn/Scripts/slr_refresh_cookies.py
```

What happens:
1. A Chrome window pops up at `partners.sexlikereal.com/user/signin`
2. You log in normally (no captcha, you're a real human)
3. Cookies save locally → SCP'd to Windows automatically
4. Daily scheduled task runs SLR for the next ~30 days, no more interaction

When daily logs start showing `SLR cookies are stale or missing`, just re-run the helper. Total recurring cost: ~30 seconds, once a month.

### Path B: Fully unattended via 2Captcha (~$1/year)

If you'd rather pay than do the monthly click:

1. Sign up at <https://2captcha.com> (email verification only)
2. Add **$5** to your balance (covers ~4 years of daily SLR refreshes at $0.003/solve)
3. Copy your API key from <https://2captcha.com/enterpage>
4. Add to **`C:\Users\andre\eclatech-hub\.env`** on Windows:
   ```
   TWOCAPTCHA_API_KEY=your_key_here
   ```
5. Daily scheduled task picks SLR up automatically the next morning

### Path C: Headed first run (one-off)

If you happen to be in front of the Windows box (RDP or directly):

```
ssh -i ~/.ssh/id_ed25519_win andre@100.90.90.68
cd C:\Users\andre\eclatech-hub
py scrape_revenue_data.py --slr --headed
```

A Chrome window pops on the Windows desktop, you click through the captcha, cookies persist for ~30 days. Same as path A but without the SCP step.

## If you ever want to disable SLR

Delete `~/.scraper_state/slr.json` on Windows AND remove `TWOCAPTCHA_API_KEY` from `.env`. The daily task will skip SLR; POVR + VRPorn keep running.

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
