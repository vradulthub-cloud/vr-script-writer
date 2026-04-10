#!/usr/bin/env python3
"""
legal_docs_dates.py
===================
Called by legal_docs_daily.sh after legal_docs_run.mjs.
Reads the JSON output from the Node script (passed via stdin or first arg),
downloads each male PDF, fills all date fields, and re-uploads to Drive.

Date fields filled in every male template:
  Date 1          — W-9 signature date
  Custom Field 13 — Model Services Agreement top-right "Dated:"
  Date 2          — Perjury/consent page "Dated:"
"""

import json
import sys
import tempfile
import urllib.request
import urllib.parse
from datetime import date
from pathlib import Path

try:
    import pypdf
    from pypdf.generic import NameObject, create_string_object
except ImportError:
    print("ERROR: pypdf not installed. Run: pip3 install pypdf", file=sys.stderr)
    sys.exit(1)

CREDS_PATH = Path.home() / ".config" / "google-legal-docs" / "credentials.json"

DATE_FIELDS = {"Date 1", "Date 2", "Custom Field 13"}


def get_access_token(creds: dict) -> str:
    params = urllib.parse.urlencode({
        "grant_type":    "refresh_token",
        "refresh_token": creds["refresh_token"],
        "client_id":     creds["client_id"],
        "client_secret": creds["client_secret"],
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=params, method="POST")
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
    if "access_token" not in data:
        raise RuntimeError("Token refresh failed: " + json.dumps(data))
    return data["access_token"]


def drive_download(file_id: str, token: str) -> bytes:
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def drive_upload(file_id: str, content: bytes, token: str) -> dict:
    url = f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=media"
    req = urllib.request.Request(url, data=content, method="PATCH", headers={
        "Authorization":  f"Bearer {token}",
        "Content-Type":   "application/pdf",
        "Content-Length": str(len(content)),
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def fill_dates(pdf_bytes: bytes, today_str: str) -> bytes:
    reader = pypdf.PdfReader(pdf_bytes if hasattr(pdf_bytes, 'read') else __import__('io').BytesIO(pdf_bytes))
    writer = pypdf.PdfWriter()
    writer.append(reader)

    filled = []
    for page in writer.pages:
        if "/Annots" not in page:
            continue
        for annot in page["/Annots"]:
            obj = annot.get_object()
            field_name = obj.get("/T")
            if field_name in DATE_FIELDS:
                obj.update({
                    NameObject("/V"):  create_string_object(today_str),
                    NameObject("/DV"): create_string_object(today_str),
                })
                filled.append(field_name)

    import io
    buf = io.BytesIO()
    writer.write(buf)
    print(f"  Filled fields: {filled}")
    return buf.getvalue()


def main():
    # Read JSON from stdin (piped from Node script)
    raw = sys.stdin.read().strip()
    if not raw:
        print("No input from Node script — nothing to do.")
        sys.exit(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not parse Node script output: {e}", file=sys.stderr)
        print(f"Raw output was: {raw[:500]}", file=sys.stderr)
        sys.exit(1)

    if "error" in data:
        print(f"ERROR from Node script: {data['error']}", file=sys.stderr)
        sys.exit(1)

    if data.get("status") == "No BG shoots today":
        print(f"No BG shoots today ({data.get('date')}) — skipping date fill.")
        sys.exit(0)

    male_files = data.get("maleFileIds", [])
    if not male_files:
        print("No male files to fill dates for.")
        sys.exit(0)

    # Load credentials and get token
    try:
        creds = json.loads(CREDS_PATH.read_text())
    except Exception as e:
        print(f"ERROR: Cannot read credentials: {e}", file=sys.stderr)
        sys.exit(1)

    token = get_access_token(creds)

    # Today's date in the same format as existing fields (e.g. "Mar 16, 2026")
    today = date.today()
    today_str = today.strftime("%b %-d, %Y")
    print(f"Filling dates with: {today_str}")

    for file_info in male_files:
        file_id   = file_info["id"]
        file_name = file_info["name"]
        print(f"\nProcessing: {file_name}")

        pdf_bytes = drive_download(file_id, token)
        filled_bytes = fill_dates(pdf_bytes, today_str)
        result = drive_upload(file_id, filled_bytes, token)

        if "error" in result:
            print(f"  ERROR uploading: {result['error']}", file=sys.stderr)
        else:
            print(f"  ✓ Updated in Drive")

    print("\nDone.")


if __name__ == "__main__":
    main()
