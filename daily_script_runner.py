#!/usr/bin/env python3
"""
daily_script_runner.py
======================
Run once daily (via cron or launchd) to:
  1. Find rows with Studio + Female but no Plot → generate scripts
  2. Find rows marked STATUS='REGEN' → regenerate those scripts

Usage:
    python3 /Users/andrewninn/Scripts/daily_script_runner.py

Cron example (runs daily at 7am):
    0 7 * * * /usr/bin/python3 /Users/andrewninn/Scripts/daily_script_runner.py >> /Users/andrewninn/Scripts/logs/daily_scripts.log 2>&1
"""

import os
import sys
import logging
from datetime import datetime
import anthropic
from script_writer import SYSTEM_PROMPT, build_prompt
from sheets_integration import (
    get_spreadsheet, month_tabs, rows_needing_scripts,
    write_script, parse_script_text,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def run():
    log.info("=== Daily Script Runner starting ===")

    try:
        sh = get_spreadsheet()
    except Exception as e:
        log.error(f"Could not open sheet: {e}")
        sys.exit(1)

    client = anthropic.Anthropic()
    tabs = month_tabs(sh)

    pending = []
    for ws in tabs:
        for row_idx, row_data in rows_needing_scripts(ws, include_regen=True):
            pending.append((ws, row_idx, row_data))

    if not pending:
        log.info("Nothing to generate — all rows up to date.")
        return

    log.info(f"Found {len(pending)} row(s) to process.")
    success, failed = 0, 0

    for ws, row_idx, row_data in pending:
        studio_val = row_data["studio"]
        female_val = row_data["female"]
        male_val   = row_data["male"]
        dest_val   = row_data["location"] or None
        scene_val  = row_data["scene_type"]
        is_regen   = row_data["status"] == "REGEN"

        action = "Regenerating" if is_regen else "Generating"
        log.info(f"{action}: {ws.title} | {studio_val} — {female_val} ({scene_val})")

        # Normalize scene type
        scene_norm = "BGCP" if "CP" in scene_val.upper() or "CREAMPIE" in scene_val.upper() else "BG"

        parsed = {
            "studio": studio_val,
            "destination": dest_val,
            "scene_type": scene_norm,
            "female": female_val,
            "male": male_val if male_val else "Mike Mancini",
        }

        try:
            prompt = build_prompt(parsed)
            full_text = ""

            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=SYSTEM_PROMPT,
                tools=[{"type": "web_search_20260209", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    full_text += chunk

            fields = parse_script_text(full_text)

            if not fields.get("plot"):
                log.warning(f"  Could not parse plot for {female_val} — skipping.")
                failed += 1
                continue

            write_script(
                ws, row_idx,
                theme=fields.get("theme", ""),
                plot=fields.get("plot", ""),
                wardrobe_female=fields.get("wardrobe_female", ""),
                wardrobe_male=fields.get("wardrobe_male", ""),
                shoot_location=fields.get("shoot_location", ""),
                set_design=fields.get("set_design", ""),
                props=fields.get("props", ""),
            )
            log.info(f"  ✓ Written to {ws.title} row {row_idx}")
            success += 1

        except Exception as e:
            log.error(f"  ✗ Error generating for {female_val}: {e}")
            failed += 1

    log.info(f"=== Done: {success} succeeded, {failed} failed ===")


if __name__ == "__main__":
    run()
