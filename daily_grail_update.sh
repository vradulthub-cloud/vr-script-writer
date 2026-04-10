#!/bin/bash
# daily_grail_update.sh
# Runs every morning at 5am via LaunchAgent.
# Checks the 2026 Scripts sheet for today's shoots and adds new
# sequential studio IDs to The Grail – Metadata Master.

set -euo pipefail

LOG_DIR="/Users/andrewninn/Scripts/logs"
mkdir -p "$LOG_DIR"

echo "=== Daily Grail Update — $(date) ==="

/usr/local/bin/python3 /Users/andrewninn/Scripts/daily_grail_update.py

echo "=== Done ==="
