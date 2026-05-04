"""Notification dispatcher — fanout layer between domain events and channels.

Domain code (uploads, descriptions, etc.) calls `dispatch(event)` with a
typed event. The dispatcher resolves *who* should be notified (based on
each user's saved prefs) and *how* (in-app, Teams, email), then posts the
message through each enabled channel.

Channels:
  - in_app:  api.routers.notifications.create_notification (existing)
  - teams:   api.teams_webhook.send                        (new)
  - email:   stub (logged only) — wire when SMTP/SendGrid is added

Channel routing rules:
  - in_app is per-recipient (one row per user).
  - Teams is broadcast — one POST to the channel, regardless of how many
    users have it enabled, so we don't spam Teams with N copies of the
    same message.
  - email is per-recipient (one send per user with email enabled).

Defaults: every event type has a default channel set, applied when a user
has no row in user_notification_prefs for that event. This means new
event types light up notifications for everyone without any setup.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from api.database import get_db
from api import teams_webhook
from api.routers import notifications as notif_router

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event catalog
# ---------------------------------------------------------------------------

# One-stop registry: event type ID, human label, description, default channels.
# Adding a new event = adding one row here, then calling dispatch(...) from
# the domain code that emits it.
EVENT_CATALOG: list[dict] = [
    {
        "type": "photos_uploaded",
        "label": "Photos uploaded",
        "description": "Fires when a photo set (.zip) finishes uploading to a scene.",
        "defaults": ["in_app", "teams"],
    },
    {
        "type": "video_uploaded",
        "label": "Video uploaded",
        "description": "Fires when a video finishes uploading to a scene.",
        "defaults": ["in_app"],
    },
    {
        "type": "description_uploaded",
        "label": "Description uploaded",
        "description": "Fires when a description doc lands in a scene's MEGA folder.",
        "defaults": ["in_app"],
    },
    {
        "type": "storyboard_uploaded",
        "label": "Storyboard uploaded",
        "description": "Fires when storyboard frames are uploaded or auto-extracted from a photoset.",
        "defaults": ["in_app"],
    },
    {
        "type": "legal_uploaded",
        "label": "Legal documents uploaded",
        "description": "Fires when a legal/2257/W-9 document lands in a scene's Legal folder.",
        "defaults": ["in_app"],
    },
    # Mirror the existing ticket events so users can opt in/out of those too.
    {
        "type": notif_router.TYPE_TICKET_CREATED,
        "label": "New ticket",
        "description": "Fires when a new ticket is filed.",
        "defaults": ["in_app"],
    },
    {
        "type": notif_router.TYPE_TICKET_STATUS,
        "label": "Ticket status change",
        "description": "Fires when a ticket you submitted changes status.",
        "defaults": ["in_app"],
    },
    {
        "type": notif_router.TYPE_TICKET_ASSIGNED,
        "label": "Ticket assigned to you",
        "description": "Fires when a ticket is assigned to you.",
        "defaults": ["in_app"],
    },
    {
        "type": notif_router.TYPE_APPROVAL_SUBMITTED,
        "label": "Approval submitted",
        "description": "Fires when content is submitted for approval.",
        "defaults": ["in_app"],
    },
    {
        "type": notif_router.TYPE_APPROVAL_DECIDED,
        "label": "Approval decided",
        "description": "Fires when an approval you submitted is approved or rejected.",
        "defaults": ["in_app"],
    },
]

EVENT_TYPES: set[str] = {e["type"] for e in EVENT_CATALOG}
ALL_CHANNELS: tuple[str, ...] = ("in_app", "teams", "email")

_DEFAULT_CHANNELS: dict[str, set[str]] = {
    e["type"]: set(e["defaults"]) for e in EVENT_CATALOG
}


# ---------------------------------------------------------------------------
# Pref lookup
# ---------------------------------------------------------------------------

def _parse_channels(raw: str) -> set[str]:
    parts = {p.strip() for p in (raw or "").split(",") if p.strip()}
    return parts & set(ALL_CHANNELS)


def _user_channels(user_email: str, event_type: str) -> set[str]:
    """Return the set of channels enabled for (user, event), falling back
    to event defaults when no row exists. Returns an empty set if the user
    has explicitly disabled the event (enabled=0)."""
    if event_type not in EVENT_TYPES:
        return set()
    try:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT channels, enabled FROM user_notification_prefs
                WHERE user_email = ? COLLATE NOCASE AND event_type = ?
                """,
                (user_email, event_type),
            ).fetchone()
    except Exception:
        _log.exception("dispatcher: pref lookup failed user=%s type=%s", user_email, event_type)
        return _DEFAULT_CHANNELS.get(event_type, set())

    if row is None:
        return _DEFAULT_CHANNELS.get(event_type, set())
    if not int(row["enabled"]):
        return set()
    return _parse_channels(row["channels"])


def _all_active_users() -> list[dict]:
    """Return [{email, name}] for every user in the users table."""
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT email, name FROM users WHERE name != ''",
            ).fetchall()
            return [{"email": r["email"], "name": r["name"]} for r in rows]
    except Exception:
        _log.exception("dispatcher: failed to load users")
        return []


# ---------------------------------------------------------------------------
# Public dispatch API
# ---------------------------------------------------------------------------

@dataclass
class NotificationEvent:
    """A domain event ready to be dispatched. ``link`` is a relative path
    in the hub (e.g. ``/missing``); the dispatcher prepends an absolute base
    when posting to external channels."""
    event_type: str
    title: str
    message: str
    link: str = ""
    # Optional explicit recipient override (Tam-style). When set, only these
    # users are notified regardless of prefs (still respecting per-user
    # disable). Useful for "@mention" style targeted notifications.
    recipients: Optional[list[str]] = None  # list of emails


def _abs_link(link: str) -> Optional[str]:
    if not link:
        return None
    if link.startswith("http://") or link.startswith("https://"):
        return link
    # Read the configured hub base URL. Falls back to a relative path so
    # Teams cards still render (the OpenUri action just won't work).
    base = ""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'hub_base_url'",
            ).fetchone()
            if row:
                base = (row["value"] or "").rstrip("/")
    except Exception:
        pass
    if not base:
        return None
    return f"{base}{link if link.startswith('/') else '/' + link}"


def dispatch(event: NotificationEvent) -> None:
    """Fan an event out to every channel each user has enabled.

    - in_app: one row per recipient via create_notification().
    - teams: a single POST to the channel webhook, only if at least one
      user has Teams enabled for this event (so unconfigured webhooks
      don't get spammed and users can opt out individually).
    - email: stubbed (logged) until SMTP/SendGrid is wired.

    Errors in any single channel are swallowed and logged — one broken
    integration must not break the others.
    """
    if event.event_type not in EVENT_TYPES:
        _log.warning("dispatcher: unknown event_type=%s — registered it in EVENT_CATALOG?", event.event_type)
        return

    users = _all_active_users()
    if event.recipients:
        wanted = {e.lower() for e in event.recipients}
        users = [u for u in users if u["email"].lower() in wanted]

    teams_enabled = False
    email_recipients: list[dict] = []

    for u in users:
        channels = _user_channels(u["email"], event.event_type)
        if not channels:
            continue
        if "in_app" in channels:
            try:
                notif_router.create_notification(
                    recipient=u["name"],
                    notif_type=event.event_type,
                    title=event.title,
                    message=event.message,
                    link=event.link,
                )
            except Exception:
                _log.exception("dispatcher: in_app create_notification failed user=%s", u["email"])
        if "teams" in channels:
            teams_enabled = True
        if "email" in channels:
            email_recipients.append(u)

    if teams_enabled:
        try:
            teams_webhook.send(
                title=event.title,
                text=event.message,
                link=_abs_link(event.link),
                link_label="Open in Eclatech Hub" if event.link else None,
            )
        except Exception:
            _log.exception("dispatcher: teams send failed event=%s", event.event_type)

    if email_recipients:
        # Stub — wire when an SMTP/SendGrid client is added. Logging here
        # so the audit trail is visible in API logs.
        for u in email_recipients:
            _log.info(
                "dispatcher: email channel enabled for %s but no email backend wired (event=%s)",
                u["email"], event.event_type,
            )


# ---------------------------------------------------------------------------
# Pref management helpers (used by the prefs router)
# ---------------------------------------------------------------------------

def get_user_prefs(user_email: str) -> list[dict]:
    """Return one row per event type — saved values when present, defaults
    when not — so the UI can render every event with a consistent shape."""
    saved: dict[str, dict] = {}
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT event_type, channels, enabled FROM user_notification_prefs
                WHERE user_email = ? COLLATE NOCASE
                """,
                (user_email,),
            ).fetchall()
            saved = {
                r["event_type"]: {
                    "channels": list(_parse_channels(r["channels"])),
                    "enabled": bool(int(r["enabled"])),
                }
                for r in rows
            }
    except Exception:
        _log.exception("dispatcher: get_user_prefs failed user=%s", user_email)

    out: list[dict] = []
    for ev in EVENT_CATALOG:
        s = saved.get(ev["type"])
        out.append({
            "event_type": ev["type"],
            "label": ev["label"],
            "description": ev["description"],
            "default_channels": list(ev["defaults"]),
            "channels": s["channels"] if s else list(ev["defaults"]),
            "enabled": s["enabled"] if s else True,
        })
    return out


def set_user_pref(
    user_email: str,
    event_type: str,
    channels: list[str],
    enabled: bool,
) -> None:
    """Upsert one preference row. Channels are filtered to known values."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type: {event_type}")
    valid = sorted({c for c in channels if c in ALL_CHANNELS})
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_notification_prefs
                (user_email, event_type, channels, enabled, updated_at)
            VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            ON CONFLICT(user_email, event_type) DO UPDATE SET
              channels = excluded.channels,
              enabled = excluded.enabled,
              updated_at = excluded.updated_at
            """,
            (user_email, event_type, ",".join(valid), 1 if enabled else 0),
        )
