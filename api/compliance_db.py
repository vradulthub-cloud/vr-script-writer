"""
Read/write helpers for the compliance_signatures table.

The Drive folder lookup remains as a transitional fallback in
compliance.py, but is_complete is sourced from this table going
forward.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from api import compliance_contract as cc
from api.database import get_db

_log = logging.getLogger(__name__)


# ─── Models ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SignedTalent:
    """Returned by list_signed_talents. Read-only summary view."""
    shoot_id: str
    talent_role: str
    talent_slug: str
    talent_display: str
    legal_name: str
    signed_at: str
    pdf_mega_path: str


# ─── Contract version ────────────────────────────────────────────────────────


def contract_version() -> str:
    """Stable hash of the verbatim contract text — recorded with each
    signature so we know exactly what wording the talent agreed to, even if
    we later edit api/compliance_contract.py."""
    h = hashlib.sha256()
    h.update(cc.CONTRACT_TITLE.encode())
    h.update(cc.CONTRACT_INTRO.encode())
    for sec in cc.AGREEMENT_SECTIONS:
        h.update(sec.id.encode())
        h.update(sec.heading.encode())
        h.update(sec.body.encode())
    for blob in (
        cc.WITNESS_STATEMENT, cc.EXECUTION_LINE,
        cc.DISCLOSURE_HEADING, cc.DISCLOSURE_STATEMENT,
        cc.DOCUMENTS_PROVIDED_HEADING,
        cc.DATA_CONSENT, cc.PERJURY_STATEMENT, cc.INDEMNITY_STATEMENT,
        cc.PRODUCER_NAME,
    ):
        h.update(blob.encode())
    for item in cc.DOCUMENTS_PROVIDED_LIST:
        h.update(item.encode())
    return f"eclatech.v1.{h.hexdigest()[:12]}"


# ─── Writes ──────────────────────────────────────────────────────────────────


def upsert_signature(
    *,
    shoot_id: str,
    shoot_date: str,
    scene_id: str,
    studio: str,
    talent_role: str,
    talent_slug: str,
    talent_display: str,
    legal_name: str,
    business_name: str,
    tax_classification: str,
    llc_class: str,
    other_classification: str,
    exempt_payee_code: str,
    fatca_code: str,
    tin_type: str,
    tin: str,
    dob: str,
    place_of_birth: str,
    street_address: str,
    city_state_zip: str,
    phone: str,
    email: str,
    id1_type: str,
    id1_number: str,
    id2_type: str,
    id2_number: str,
    stage_names: str,
    professional_names: str,
    nicknames_aliases: str,
    previous_legal_names: str,
    signature_image_path: str,
    signed_ip: str,
    signed_user_agent: str,
    signed_by_user: str,
    pdf_local_path: str,
    pdf_mega_path: str,
) -> int:
    """Insert or replace the row keyed by (shoot_id, talent_role, talent_slug).
    Returns the row id."""
    signed_at = _utcnow()
    version = contract_version()
    with get_db() as conn:
        # SQLite UPSERT via ON CONFLICT — preserves id when replacing
        cur = conn.execute(
            """
            INSERT INTO compliance_signatures (
                shoot_id, shoot_date, scene_id, studio,
                talent_role, talent_slug, talent_display,
                legal_name, business_name,
                tax_classification, llc_class, other_classification,
                exempt_payee_code, fatca_code,
                tin_type, tin,
                dob, place_of_birth, street_address, city_state_zip,
                phone, email,
                id1_type, id1_number, id2_type, id2_number,
                stage_names, professional_names, nicknames_aliases, previous_legal_names,
                signature_image_path, signed_at, signed_ip, signed_user_agent,
                signed_by_user, contract_version,
                pdf_local_path, pdf_mega_path
            )
            VALUES (
                :shoot_id, :shoot_date, :scene_id, :studio,
                :talent_role, :talent_slug, :talent_display,
                :legal_name, :business_name,
                :tax_classification, :llc_class, :other_classification,
                :exempt_payee_code, :fatca_code,
                :tin_type, :tin,
                :dob, :place_of_birth, :street_address, :city_state_zip,
                :phone, :email,
                :id1_type, :id1_number, :id2_type, :id2_number,
                :stage_names, :professional_names, :nicknames_aliases, :previous_legal_names,
                :signature_image_path, :signed_at, :signed_ip, :signed_user_agent,
                :signed_by_user, :contract_version,
                :pdf_local_path, :pdf_mega_path
            )
            ON CONFLICT(shoot_id, talent_role, talent_slug) DO UPDATE SET
                shoot_date=excluded.shoot_date,
                scene_id=excluded.scene_id,
                studio=excluded.studio,
                talent_display=excluded.talent_display,
                legal_name=excluded.legal_name,
                business_name=excluded.business_name,
                tax_classification=excluded.tax_classification,
                llc_class=excluded.llc_class,
                other_classification=excluded.other_classification,
                exempt_payee_code=excluded.exempt_payee_code,
                fatca_code=excluded.fatca_code,
                tin_type=excluded.tin_type,
                tin=excluded.tin,
                dob=excluded.dob,
                place_of_birth=excluded.place_of_birth,
                street_address=excluded.street_address,
                city_state_zip=excluded.city_state_zip,
                phone=excluded.phone,
                email=excluded.email,
                id1_type=excluded.id1_type,
                id1_number=excluded.id1_number,
                id2_type=excluded.id2_type,
                id2_number=excluded.id2_number,
                stage_names=excluded.stage_names,
                professional_names=excluded.professional_names,
                nicknames_aliases=excluded.nicknames_aliases,
                previous_legal_names=excluded.previous_legal_names,
                signature_image_path=excluded.signature_image_path,
                signed_at=excluded.signed_at,
                signed_ip=excluded.signed_ip,
                signed_user_agent=excluded.signed_user_agent,
                signed_by_user=excluded.signed_by_user,
                contract_version=excluded.contract_version,
                pdf_local_path=excluded.pdf_local_path,
                pdf_mega_path=excluded.pdf_mega_path
            """,
            {
                "shoot_id": shoot_id, "shoot_date": shoot_date,
                "scene_id": scene_id, "studio": studio,
                "talent_role": talent_role, "talent_slug": talent_slug,
                "talent_display": talent_display,
                "legal_name": legal_name, "business_name": business_name,
                "tax_classification": tax_classification,
                "llc_class": llc_class, "other_classification": other_classification,
                "exempt_payee_code": exempt_payee_code, "fatca_code": fatca_code,
                "tin_type": tin_type, "tin": tin,
                "dob": dob, "place_of_birth": place_of_birth,
                "street_address": street_address, "city_state_zip": city_state_zip,
                "phone": phone, "email": email,
                "id1_type": id1_type, "id1_number": id1_number,
                "id2_type": id2_type, "id2_number": id2_number,
                "stage_names": stage_names,
                "professional_names": professional_names,
                "nicknames_aliases": nicknames_aliases,
                "previous_legal_names": previous_legal_names,
                "signature_image_path": signature_image_path,
                "signed_at": signed_at,
                "signed_ip": signed_ip,
                "signed_user_agent": signed_user_agent,
                "signed_by_user": signed_by_user,
                "contract_version": version,
                "pdf_local_path": pdf_local_path,
                "pdf_mega_path": pdf_mega_path,
            },
        )
        return cur.lastrowid or 0


# ─── Reads ───────────────────────────────────────────────────────────────────


def list_signed_talents(shoot_ids: list[str]) -> dict[str, list[SignedTalent]]:
    """Bulk-load signed talents for a set of shoot_ids.
    Returns {shoot_id: [SignedTalent, ...]} with shoots that have no rows
    omitted."""
    if not shoot_ids:
        return {}
    placeholders = ",".join("?" * len(shoot_ids))
    out: dict[str, list[SignedTalent]] = {}
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT shoot_id, talent_role, talent_slug, talent_display,
                       legal_name, signed_at, pdf_mega_path
                  FROM compliance_signatures
                 WHERE shoot_id IN ({placeholders})""",
            shoot_ids,
        ).fetchall()
    for r in rows:
        d = dict(r)
        out.setdefault(d["shoot_id"], []).append(SignedTalent(
            shoot_id=d["shoot_id"],
            talent_role=d["talent_role"],
            talent_slug=d["talent_slug"],
            talent_display=d["talent_display"],
            legal_name=d["legal_name"],
            signed_at=d["signed_at"],
            pdf_mega_path=d["pdf_mega_path"] or "",
        ))
    return out


def get_signed_pdf_path(shoot_id: str, talent_role: str, talent_slug: str) -> Optional[str]:
    """Look up the local PDF path written by the most recent sign event."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT pdf_local_path FROM compliance_signatures
                WHERE shoot_id=? AND talent_role=? AND talent_slug=?""",
            (shoot_id, talent_role, talent_slug),
        ).fetchone()
    return (row["pdf_local_path"] if row else None) or None


def is_shoot_complete(shoot_id: str, has_male: bool) -> bool:
    """A shoot is complete when every required talent role has a signature row.
    For a female-only BG, that means 1 row with talent_role='female'.
    For a BG with male, both 'female' and 'male' rows are required."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT talent_role FROM compliance_signatures WHERE shoot_id=?""",
            (shoot_id,),
        ).fetchall()
    roles = {r["talent_role"] for r in rows}
    needed = {"female", "male"} if has_male else {"female"}
    return needed.issubset(roles)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
