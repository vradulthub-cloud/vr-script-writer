"""CLI runner for the MEGA legal-folder scraper.

Run from the eclatech-hub root on the Windows API host:

    "C:\\Program Files\\Python311\\python.exe" scrape_mega_legal.py
    "C:\\Program Files\\Python311\\python.exe" scrape_mega_legal.py --studio vra
    "C:\\Program Files\\Python311\\python.exe" scrape_mega_legal.py --link

Logs to Dropbox/AudioTraining/scrape_mega_legal.log so the Mac can monitor
without SSH (per memory rule about SSH child-process lifecycle).

Exit code 0 on success, 1 on any error.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure relative imports work when run from the eclatech-hub root.
sys.path.insert(0, ".")


def _setup_logging(log_path: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Index MEGA Legal/ folders into compliance_legal_files")
    parser.add_argument(
        "--studio", default="",
        help="Restrict to one studio code (fpvr/vrh/vra/njoi). Default: all four.",
    )
    parser.add_argument(
        "--link", action="store_true",
        help="After indexing, link rows to existing compliance_signatures via pdf_mega_path.",
    )
    parser.add_argument(
        "--log",
        default="",
        help="Optional log-file path (default: ./logs/scrape_mega_legal.log)",
    )
    args = parser.parse_args()

    log_path = Path(args.log) if args.log else Path("logs/scrape_mega_legal.log")
    _setup_logging(log_path)

    log = logging.getLogger("scrape_mega_legal")
    log.info("starting scan studios=%s link=%s", args.studio or "all", args.link)

    from api.compliance_scraper import (
        DEFAULT_STUDIOS,
        link_imported_signatures,
        run_scan,
    )

    studios = (args.studio.lower(),) if args.studio else DEFAULT_STUDIOS
    try:
        summary = run_scan(studios)
    except Exception as exc:
        log.exception("scan failed: %s", exc)
        return 1

    log.info("scan summary: %s", json.dumps(summary, default=str))

    if args.link:
        try:
            linked = link_imported_signatures()
            log.info("linked %d files to compliance_signatures rows", linked)
        except Exception as exc:
            log.exception("link step failed: %s", exc)
            return 1

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
