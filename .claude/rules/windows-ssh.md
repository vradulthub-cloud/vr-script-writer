---
paths:
  - "sync_mega_staging.py"
  - "daily_grail_update.sh"
  - "sync_training_to_dropbox.py"
---

# Windows SSH Lessons (DO NOT REPEAT)

- `Start-Process -WindowStyle Hidden` via SSH DOES NOT work — process dies on disconnect
- `start /b` via SSH DOES NOT work — same problem
- ONLY reliable method: `launch_training.ps1` using ProcessStartInfo + WaitForExit via `Register-ScheduledTask`
- Training logs MUST go to Dropbox so Mac can monitor without SSH
- SSH on Windows kills child processes on disconnect — always use Task Scheduler
