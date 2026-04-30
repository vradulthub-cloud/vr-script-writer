"""set_s4_cors.py — configure CORS on the four MEGA S4 buckets so the hub UI
can multipart-upload directly from the browser.

The Uploads dashboard PUTs each 64 MB part to a presigned URL on
``{bucket}.s3.g.s4.mega.io``. That browser-origin PUT only works if the bucket
has a CORS policy that:

  - allows the hub's origin(s)
  - allows the PUT method
  - exposes the ``ETag`` response header (the browser needs it to feed
    ``CompleteMultipartUpload``).

Usage:

    python3 set_s4_cors.py probe                  # show current CORS per bucket
    python3 set_s4_cors.py apply                  # apply default policy to all 4
    python3 set_s4_cors.py apply --bucket vrh     # apply to one
    python3 set_s4_cors.py apply --origin https://hub.example.com [--origin ...]
    python3 set_s4_cors.py revoke --bucket fpvr   # for the Path-B fallback test
    python3 set_s4_cors.py browser-probe          # one-shot HEAD from boto3 to
                                                  # confirm the request can be
                                                  # signed against the endpoint

If MEGA S4 rejects ``put_bucket_cors`` outright, ``apply`` fails loudly. That's
the gating signal that we have to ship Path B (proxy through FastAPI) only.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable

from botocore.exceptions import ClientError

import s4_client


DEFAULT_ORIGINS = [
    # Production hub origin(s) — fill in via --origin once final URL is known.
    "https://hub.eclatech.studio",
    "https://eclatech-hub.vercel.app",
    # Vercel preview deploys: S3 CORS supports a single leading asterisk.
    "https://*-vradulthub-cloud.vercel.app",
    # Local dev.
    "http://localhost:3000",
    "http://localhost:3001",
]


def _build_cors_rules(origins: Iterable[str]) -> dict:
    return {
        "CORSRules": [
            {
                "ID": "hub-uploads-direct",
                "AllowedOrigins": list(origins),
                "AllowedMethods": ["GET", "HEAD", "PUT", "POST", "DELETE"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag", "x-amz-version-id"],
                "MaxAgeSeconds": 3600,
            }
        ]
    }


def cmd_probe(buckets: list[str]) -> int:
    client = s4_client._client()
    rc = 0
    for bucket in buckets:
        try:
            resp = client.get_bucket_cors(Bucket=bucket)
            print(f"== {bucket} ==")
            print(json.dumps(resp.get("CORSRules", []), indent=2, default=str))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchCORSConfiguration", "NoSuchCORSConfig"):
                print(f"== {bucket} == (no CORS configured)")
            else:
                print(f"== {bucket} == ERROR: {exc}")
                rc = 2
    return rc


def cmd_apply(buckets: list[str], origins: list[str], dry_run: bool) -> int:
    rules = _build_cors_rules(origins)
    client = s4_client._client()
    if dry_run:
        print("(dry-run) would apply:")
        print(json.dumps(rules, indent=2))
        print(f"to buckets: {', '.join(buckets)}")
        return 0
    rc = 0
    for bucket in buckets:
        try:
            client.put_bucket_cors(Bucket=bucket, CORSConfiguration=rules)
            print(f"  OK  {bucket}: CORS applied")
        except ClientError as exc:
            print(f"  ERR {bucket}: {exc}")
            rc = 2
    return rc


def cmd_revoke(buckets: list[str]) -> int:
    client = s4_client._client()
    rc = 0
    for bucket in buckets:
        try:
            client.delete_bucket_cors(Bucket=bucket)
            print(f"  OK  {bucket}: CORS removed")
        except ClientError as exc:
            print(f"  ERR {bucket}: {exc}")
            rc = 2
    return rc


def cmd_browser_probe(buckets: list[str]) -> int:
    """Check whether a presigned PUT URL is generated correctly. Doesn't
    actually upload — just shows the URL shape and confirms boto3 can sign
    upload_part requests against the endpoint."""
    client = s4_client._client()
    rc = 0
    for bucket in buckets:
        try:
            url = client.generate_presigned_url(
                "put_object",
                Params={"Bucket": bucket, "Key": "cors-probe.txt",
                        "ContentType": "text/plain"},
                ExpiresIn=300,
            )
            print(f"  OK  {bucket}: {url[:120]}...")
        except Exception as exc:
            print(f"  ERR {bucket}: {exc}")
            rc = 2
    return rc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("probe", "apply", "revoke", "browser-probe"):
        sp = sub.add_parser(name)
        sp.add_argument("--bucket", action="append", default=[],
                        help="Repeat to limit to specific buckets. "
                             "Default: all four (fpvr/vrh/vra/njoi).")
        if name == "apply":
            sp.add_argument("--origin", action="append", default=[],
                            help="Repeat to set allowed origins. Default: see "
                                 "DEFAULT_ORIGINS in source.")
            sp.add_argument("--dry-run", action="store_true")

    args = p.parse_args()
    buckets = args.bucket or list(s4_client.STUDIO_BUCKETS.values())
    if args.cmd == "probe":
        return cmd_probe(buckets)
    if args.cmd == "apply":
        origins = args.origin or DEFAULT_ORIGINS
        return cmd_apply(buckets, origins, args.dry_run)
    if args.cmd == "revoke":
        return cmd_revoke(buckets)
    if args.cmd == "browser-probe":
        return cmd_browser_probe(buckets)
    return 2


if __name__ == "__main__":
    sys.exit(main())
