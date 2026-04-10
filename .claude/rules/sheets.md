---
paths:
  - "sheets_integration.py"
  - "daily_grail_update.py"
  - "ticket_tools.py"
  - "fill_profile_stats.py"
  - "beautify_sheet.py"
  - "update_roster.py"
  - "weekly_roster_update.py"
  - "backfill_dates_booked.py"
  - "calculate_avg_rates.py"
---

# Google Sheets Rules

## Sheet IDs
| Sheet | ID | Tabs |
|-------|----|------|
| Scripts | `1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ` | Monthly: "January 2026", etc. |
| Grail | `1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk` | FPVR, VRH, VRA, NNJOI |
| Tickets | `1t92DvQxZzgHKjp4-uxaPLdyaqlmcGNLxSd6qx8hANyA` | Sheet1 (tickets), Users (auth) |
| Budgets | `1bM1G49p2KK9WY3WfjzPixrWUw8KBiDGKR-0jKw5QUVc` | Monthly tabs |
| Booking | `1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw` | Agency tabs |
| Comp Planning | `1i6W4eZ8Bva3HvVmhpAVgjeHwfqbARkwBZ38aUhriaGs` | FPVR/VRH/VRA Compilations |

Service account: `service_account.json` (NEVER commit this file)

## Scripts Sheet Columns (0-indexed)
A=Date, B=Studio, C=Location, D=Scene, E=Female, F=Male, G=Theme, H=WardrobeF, I=WardrobeM, J=Plot, K=Title, L=Props, M=Status

## Grail Columns
A=SiteCode, B=SceneID, C=ReleaseDate, D=Title, E=Performers, F=Categories, G=Tags

## Studio Name Mapping (CRITICAL — different everywhere)
| Context | FPVR | VRH | VRA | NJOI |
|---------|------|-----|-----|------|
| App UI | FuckPassVR | VRHush | VRAllure | NaughtyJOI |
| Scripts Sheet | FuckPassVR | VRHush | VRAllure | NaughtyJOI |
| Grail Tabs | FPVR | VRH | VRA | NNJOI |
| MEGA Folders | Grail/FPVR | Grail/VRH | Grail/VRA | Grail/NNJOI |
| Site Codes | fpvr | vrh | vra | njoi |

## References
- Shoot Budgets: `1bM1G49p2KK9WY3WfjzPixrWUw8KBiDGKR-0jKw5QUVc` — use F1 Agency column (col I) to verify model's current agency
- Local budget files: `/Users/andrewninn/Scripts/shoot_budgets/` (2021-2026 xlsx)
- VRPorn data: SLR and VRPorn are same revenue stream. Per-studio xlsx at `/Users/andrewninn/Documents/drive-download-20260317T015637Z-3-001/`
