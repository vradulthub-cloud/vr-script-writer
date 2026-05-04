"""Microsoft Teams webhook integration.

Posts JSON-formatted messages to a Teams channel via either:
  - A Power Automate "Workflows" webhook (recommended; the modern path), or
  - A legacy Office 365 connector "Incoming Webhook" URL.

Both variants accept the same MessageCard / Adaptive Card payload, so the
helper just POSTs JSON and lets Teams render it.

The webhook URL is stored in app_settings under the key "teams_webhook_url"
and managed by admins via the integrations panel. We never log the URL —
treat it as a secret (anyone with it can post to the channel).

Usage:
    from api import teams_webhook
    teams_webhook.send(
        title="Photos uploaded",
        text="Sofia Cruz / Mark Stone — VRH0762",
        link="https://hub.example.com/missing",
        link_label="Open scene",
    )
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Optional

from api.database import get_db

_log = logging.getLogger(__name__)

_SETTING_KEY = "teams_webhook_url"


def get_webhook_url() -> str:
    """Return the configured Teams webhook URL, or empty string if unset."""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (_SETTING_KEY,),
            ).fetchone()
            return (row["value"] if row else "") or ""
    except Exception:
        _log.exception("teams_webhook: failed to read setting")
        return ""


def set_webhook_url(url: str, updated_by: str = "") -> None:
    """Persist the Teams webhook URL. Pass empty string to disable Teams."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_by, updated_at)
            VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_by = excluded.updated_by,
              updated_at = excluded.updated_at
            """,
            (_SETTING_KEY, url.strip(), updated_by),
        )


def _build_payload(
    title: str,
    text: str,
    link: Optional[str] = None,
    link_label: Optional[str] = None,
) -> dict:
    """Build a MessageCard payload accepted by both Workflows and legacy
    Incoming Webhook connectors. Adaptive Cards would be more modern but
    require a slightly different envelope per webhook type — MessageCard
    still works on both as of 2026-05."""
    card: dict = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "themeColor": "BED62F",  # Eclatech lime
        "title": title,
        "text": text,
    }
    if link:
        card["potentialAction"] = [
            {
                "@type": "OpenUri",
                "name": link_label or "Open",
                "targets": [{"os": "default", "uri": link}],
            },
        ]
    return card


def _post_blocking(url: str, payload: dict) -> tuple[bool, str]:
    """POST to the webhook synchronously. Returns (ok, error_message)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.getcode()
            if status >= 400:
                return False, f"HTTP {status}"
            return True, ""
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        return False, f"URL error: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def send(
    title: str,
    text: str,
    link: Optional[str] = None,
    link_label: Optional[str] = None,
    block: bool = False,
) -> bool:
    """Send a Teams message. Returns True if the message was queued/sent.

    By default (block=False) the POST runs in a background thread so this
    never blocks the caller — fire-and-forget. Set block=True to wait for
    delivery (used by the admin "Send test message" button to surface
    errors).
    """
    url = get_webhook_url()
    if not url:
        _log.debug("teams_webhook: not configured; skipping send")
        return False

    payload = _build_payload(title=title, text=text, link=link, link_label=link_label)

    if block:
        ok, err = _post_blocking(url, payload)
        if not ok:
            _log.warning("teams_webhook: send failed: %s", err)
        return ok

    def _run() -> None:
        ok, err = _post_blocking(url, payload)
        if not ok:
            _log.warning("teams_webhook: send failed: %s", err)

    threading.Thread(target=_run, daemon=True).start()
    return True


def send_test(updated_by: str = "") -> tuple[bool, str]:
    """Send a one-off test message; returns (ok, error_message). Used by
    the admin UI to verify the webhook URL after saving it."""
    url = get_webhook_url()
    if not url:
        return False, "Teams webhook URL is not configured."
    payload = _build_payload(
        title="Eclatech Hub — webhook test",
        text=f"Test message from {updated_by or 'Eclatech Hub'}. If you can read this, the integration works.",
    )
    return _post_blocking(url, payload)
