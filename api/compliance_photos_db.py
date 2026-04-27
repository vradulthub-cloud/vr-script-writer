"""
Read/write helpers for the compliance_photos table.

Photos are independent of signatures and the legacy Drive flow — they are
captured at any time during the day and persist server-side so the iPad
shows them again on the next visit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from api.database import get_db

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredPhoto:
    shoot_id: str
    slot_id: str
    talent_role: str
    label: str
    mime_type: str
    file_size: int
    local_path: str
    mega_path: str
    uploaded_at: str


def upsert_photo(
    *,
    shoot_id: str,
    shoot_date: str,
    scene_id: str,
    studio: str,
    slot_id: str,
    talent_role: str,
    label: str,
    mime_type: str,
    file_size: int,
    local_path: str,
    mega_path: str,
    uploaded_by: str,
) -> int:
    uploaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO compliance_photos (
                shoot_id, shoot_date, scene_id, studio,
                slot_id, talent_role, label, mime_type, file_size,
                local_path, mega_path, uploaded_by, uploaded_at
            )
            VALUES (
                :shoot_id, :shoot_date, :scene_id, :studio,
                :slot_id, :talent_role, :label, :mime_type, :file_size,
                :local_path, :mega_path, :uploaded_by, :uploaded_at
            )
            ON CONFLICT(shoot_id, slot_id) DO UPDATE SET
                shoot_date=excluded.shoot_date,
                scene_id=excluded.scene_id,
                studio=excluded.studio,
                talent_role=excluded.talent_role,
                label=excluded.label,
                mime_type=excluded.mime_type,
                file_size=excluded.file_size,
                local_path=excluded.local_path,
                mega_path=excluded.mega_path,
                uploaded_by=excluded.uploaded_by,
                uploaded_at=excluded.uploaded_at
            """,
            {
                "shoot_id": shoot_id, "shoot_date": shoot_date,
                "scene_id": scene_id, "studio": studio,
                "slot_id": slot_id, "talent_role": talent_role,
                "label": label, "mime_type": mime_type, "file_size": file_size,
                "local_path": local_path, "mega_path": mega_path,
                "uploaded_by": uploaded_by, "uploaded_at": uploaded_at,
            },
        )
        return cur.lastrowid or 0


def list_photos(shoot_id: str) -> list[StoredPhoto]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT shoot_id, slot_id, talent_role, label, mime_type, file_size,
                       local_path, mega_path, uploaded_at
                  FROM compliance_photos
                 WHERE shoot_id=?
                 ORDER BY uploaded_at""",
            (shoot_id,),
        ).fetchall()
    return [
        StoredPhoto(
            shoot_id=r["shoot_id"],
            slot_id=r["slot_id"],
            talent_role=r["talent_role"] or "",
            label=r["label"],
            mime_type=r["mime_type"],
            file_size=r["file_size"] or 0,
            local_path=r["local_path"],
            mega_path=r["mega_path"] or "",
            uploaded_at=r["uploaded_at"],
        )
        for r in rows
    ]


def get_photo(shoot_id: str, slot_id: str) -> Optional[StoredPhoto]:
    with get_db() as conn:
        r = conn.execute(
            """SELECT shoot_id, slot_id, talent_role, label, mime_type, file_size,
                       local_path, mega_path, uploaded_at
                  FROM compliance_photos
                 WHERE shoot_id=? AND slot_id=?""",
            (shoot_id, slot_id),
        ).fetchone()
    if not r:
        return None
    return StoredPhoto(
        shoot_id=r["shoot_id"],
        slot_id=r["slot_id"],
        talent_role=r["talent_role"] or "",
        label=r["label"],
        mime_type=r["mime_type"],
        file_size=r["file_size"] or 0,
        local_path=r["local_path"],
        mega_path=r["mega_path"] or "",
        uploaded_at=r["uploaded_at"],
    )


def delete_photo(shoot_id: str, slot_id: str) -> Optional[StoredPhoto]:
    """Delete the row and return what was there (so caller can unlink the file)."""
    p = get_photo(shoot_id, slot_id)
    if not p:
        return None
    with get_db() as conn:
        conn.execute(
            "DELETE FROM compliance_photos WHERE shoot_id=? AND slot_id=?",
            (shoot_id, slot_id),
        )
    return p


def count_by_shoot(shoot_ids: list[str]) -> dict[str, int]:
    if not shoot_ids:
        return {}
    placeholders = ",".join("?" * len(shoot_ids))
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT shoot_id, COUNT(*) AS n
                  FROM compliance_photos
                 WHERE shoot_id IN ({placeholders})
              GROUP BY shoot_id""",
            shoot_ids,
        ).fetchall()
    return {r["shoot_id"]: int(r["n"]) for r in rows}
