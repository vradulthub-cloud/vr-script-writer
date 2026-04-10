#!/bin/bash
# legal_docs_daily.sh
# Runs every morning at 6am via LaunchAgent.
# 1. Creates Drive folders + copies PDF templates for today's BG shoots
# 2. Fills all date fields in the male PDFs

set -euo pipefail

LOG_DIR="/Users/andrewninn/Scripts/logs"
mkdir -p "$LOG_DIR"

echo "=== Legal Docs Daily — $(date) ==="

NODE_OUT=$(/opt/homebrew/bin/node /Users/andrewninn/Scripts/legal_docs_run.mjs)
echo "Node output: $NODE_OUT"

echo "$NODE_OUT" | /usr/local/bin/python3 /Users/andrewninn/Scripts/legal_docs_dates.py

echo "=== Done ==="
