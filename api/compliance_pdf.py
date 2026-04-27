"""
Generate the talent agreement PDF from the verbatim text in
api/compliance_contract.py.

Replaces the old "copy a template from Drive and stamp form fields"
flow. Now the Hub owns the contract end to end:
  - Verbatim text from compliance_contract.py
  - Form values stamped semantically (no "Custom Field 27" gymnastics)
  - Drawn signature image embedded in the signature line
  - Output written to a local temp path; the caller uploads to MEGA

Output layout (one PDF, ~5–6 pages):
  Page 1   Form W-9 (boilerplate IRS form, filled with talent's tax data)
  Page 2-4 Model Services Agreement (sections 1–11 + witness statement)
  Page 4-5 18 U.S.C. § 2257 Performer Names Disclosure
  Page 5-6 Data-processing consent + perjury statement + indemnity + signature
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageTemplate,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors

from api import compliance_contract as cc


# ─── Public API ──────────────────────────────────────────────────────────────


def render_agreement_pdf(
    *,
    talent_display: str,
    talent_role: str,                # 'female' | 'male'
    legal_name: str,
    business_name: str,
    tax_classification: str,
    llc_class: str,
    other_classification: str,
    exempt_payee_code: str,
    fatca_code: str,
    tin_type: str,                   # 'ssn' | 'ein'
    tin: str,                        # raw digits; we mask to last-4 in display
    dob: str,                        # YYYY-MM-DD
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
    signature_png_bytes: bytes,
    shoot_date: date,
    signed_at_iso: str,
    output_path: Path,
) -> None:
    """Write a full talent-agreement PDF to `output_path`."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        title=f"{talent_display} — Eclatech Performer Agreement",
        author=cc.PRODUCER_NAME,
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="main",
    )

    def _footer(canv, _doc):
        canv.saveState()
        canv.setFont("Helvetica", 8)
        canv.setFillGray(0.5)
        canv.drawString(
            doc.leftMargin, 0.5 * inch,
            f"{talent_display} — {cc.PRODUCER_NAME} performer agreement — {shoot_date.isoformat()}",
        )
        canv.drawRightString(
            letter[0] - doc.rightMargin, 0.5 * inch,
            f"Page {canv.getPageNumber()}",
        )
        canv.restoreState()

    doc.addPageTemplates([PageTemplate(id="default", frames=[frame], onPage=_footer)])

    story = []
    story += _w9_page(
        legal_name=legal_name,
        business_name=business_name,
        tax_classification=tax_classification,
        llc_class=llc_class,
        other_classification=other_classification,
        exempt_payee_code=exempt_payee_code,
        fatca_code=fatca_code,
        street_address=street_address,
        city_state_zip=city_state_zip,
        tin_type=tin_type,
        tin=tin,
        signature_png_bytes=signature_png_bytes,
        signed_at_iso=signed_at_iso,
        shoot_date=shoot_date,
    )
    story.append(PageBreak())

    story += _agreement_pages(
        talent_display=talent_display,
        legal_name=legal_name,
        signature_png_bytes=signature_png_bytes,
        shoot_date=shoot_date,
    )
    story.append(PageBreak())

    story += _disclosure_pages(
        legal_name=legal_name,
        dob=dob,
        place_of_birth=place_of_birth,
        street_address=street_address,
        city_state_zip=city_state_zip,
        phone=phone,
        email=email,
        id1_type=id1_type,
        id1_number=id1_number,
        id2_type=id2_type,
        id2_number=id2_number,
        stage_names=stage_names,
        professional_names=professional_names,
        nicknames_aliases=nicknames_aliases,
        previous_legal_names=previous_legal_names,
        talent_display=talent_display,
        signature_png_bytes=signature_png_bytes,
        shoot_date=shoot_date,
    )

    doc.build(story)


# ─── Styles ──────────────────────────────────────────────────────────────────


_BASE = getSampleStyleSheet()

_H1 = ParagraphStyle(
    "h1", parent=_BASE["Heading1"],
    fontName="Helvetica-Bold", fontSize=14, leading=18,
    spaceBefore=8, spaceAfter=8, alignment=TA_LEFT,
)
_H2 = ParagraphStyle(
    "h2", parent=_BASE["Heading2"],
    fontName="Helvetica-Bold", fontSize=11, leading=14,
    spaceBefore=10, spaceAfter=4, alignment=TA_LEFT,
)
_BODY = ParagraphStyle(
    "body", parent=_BASE["BodyText"],
    fontName="Helvetica", fontSize=9.5, leading=13,
    spaceBefore=2, spaceAfter=4, alignment=TA_JUSTIFY,
)
_LABEL = ParagraphStyle(
    "label", parent=_BASE["BodyText"],
    fontName="Helvetica-Bold", fontSize=8.5, leading=11,
    textColor=colors.grey, spaceBefore=2, spaceAfter=0,
)
_VALUE = ParagraphStyle(
    "value", parent=_BASE["BodyText"],
    fontName="Helvetica", fontSize=10, leading=13,
    spaceBefore=0, spaceAfter=4,
)
_SMALL_CENTER = ParagraphStyle(
    "small_center", parent=_BASE["BodyText"],
    fontName="Helvetica", fontSize=8, leading=10,
    alignment=TA_CENTER, textColor=colors.grey,
)


def _esc(s: str) -> str:
    """HTML-escape so Platypus Paragraph treats text literally — protects
    angle brackets in the verbatim contract (e.g. "<YOUR JURISDICTION>")
    and any user-supplied form values from being eaten as XML."""
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ─── Page builders ───────────────────────────────────────────────────────────


def _w9_page(
    *,
    legal_name: str,
    business_name: str,
    tax_classification: str,
    llc_class: str,
    other_classification: str,
    exempt_payee_code: str,
    fatca_code: str,
    street_address: str,
    city_state_zip: str,
    tin_type: str,
    tin: str,
    signature_png_bytes: bytes,
    signed_at_iso: str,
    shoot_date: date,
) -> list:
    """Form W-9 — captured from the talent's submission."""
    out: list = []
    out.append(Paragraph(_esc("Form W-9 — Request for Taxpayer Identification Number and Certification"), _H1))
    out.append(Paragraph(
        _esc(
            "(Rev. October 2018) — Department of the Treasury, Internal Revenue Service. "
            "Give Form to the requester. Do not send to the IRS."
        ),
        _SMALL_CENTER,
    ))
    out.append(Spacer(1, 10))

    # Field grid
    rows = [
        ("1. Name (as shown on your income tax return)",  legal_name),
        ("2. Business name / disregarded entity name",     business_name or "—"),
        ("3. Federal tax classification",                   _tax_class_label(tax_classification, llc_class, other_classification)),
        ("4. Exemptions — exempt payee code",               exempt_payee_code or "—"),
        ("4. Exemptions — FATCA reporting code",            fatca_code or "—"),
        ("5. Address",                                       street_address),
        ("6. City, state, ZIP",                              city_state_zip),
    ]
    out.append(_label_value_table(rows))
    out.append(Spacer(1, 14))

    # TIN block
    tin_label = "Social security number" if tin_type == "ssn" else "Employer identification number"
    out.append(Paragraph(_esc("Part I — Taxpayer Identification Number (TIN)"), _H2))
    out.append(_label_value_table([(tin_label, _format_tin(tin, tin_type))]))
    out.append(Spacer(1, 12))

    # Certification + signature
    out.append(Paragraph(_esc("Part II — Certification"), _H2))
    out.append(Paragraph(
        _esc(
            "Under penalties of perjury, I certify that: "
            "(1) The number shown on this form is my correct taxpayer identification number "
            "(or I am waiting for a number to be issued to me); "
            "(2) I am not subject to backup withholding because: (a) I am exempt from backup "
            "withholding, or (b) I have not been notified by the Internal Revenue Service "
            "(IRS) that I am subject to backup withholding as a result of a failure to "
            "report all interest or dividends, or (c) the IRS has notified me that I am no "
            "longer subject to backup withholding; "
            "(3) I am a U.S. citizen or other U.S. person (defined below); and "
            "(4) The FATCA code(s) entered on this form (if any) indicating that I am "
            "exempt from FATCA reporting is correct."
        ),
        _BODY,
    ))
    out.append(Spacer(1, 8))
    out.append(_signature_block(signature_png_bytes, legal_name, signed_at_iso, shoot_date))
    return out


def _agreement_pages(
    *,
    talent_display: str,
    legal_name: str,
    signature_png_bytes: bytes,
    shoot_date: date,
) -> list:
    out: list = []
    out.append(Paragraph(
        _esc(f"Dated: {_long_date(shoot_date)}"),
        ParagraphStyle("dated", parent=_BODY, fontName="Helvetica-Bold", spaceAfter=10),
    ))
    out.append(Paragraph(_esc(cc.CONTRACT_TITLE.upper()), _H1))
    out.append(Paragraph(_esc(cc.CONTRACT_INTRO), _BODY))
    out.append(Spacer(1, 6))

    for sec in cc.AGREEMENT_SECTIONS:
        out.append(Paragraph(_esc(sec.heading), _H2))
        for para in sec.body.split("\n\n"):
            out.append(Paragraph(_esc(para), _BODY))

    out.append(Spacer(1, 8))
    out.append(Paragraph(_esc(cc.WITNESS_STATEMENT), _BODY))
    out.append(Spacer(1, 8))
    out.append(Paragraph(_esc(cc.EXECUTION_LINE), _BODY))
    out.append(Spacer(1, 14))
    out.append(_two_col_signatures(
        producer_name=cc.PRODUCER_NAME,
        legal_name=legal_name,
        talent_display=talent_display,
        signature_png_bytes=signature_png_bytes,
        shoot_date=shoot_date,
    ))
    return out


def _disclosure_pages(
    *,
    legal_name: str,
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
    talent_display: str,
    signature_png_bytes: bytes,
    shoot_date: date,
) -> list:
    out: list = []
    out.append(Paragraph(_esc(cc.DISCLOSURE_HEADING), _H1))
    out.append(Paragraph(
        f"<b>Production Name:</b> {_esc('Eclatech LLC studio production')} "
        f"({_esc(_long_date(shoot_date))}). <b>Producer Name:</b> {_esc(cc.PRODUCER_NAME)}.",
        _BODY,
    ))
    out.append(Paragraph(
        f"I, <b>{_esc(legal_name)}</b>, " + _esc(cc.DISCLOSURE_STATEMENT.lstrip("I ")),
        _BODY,
    ))
    out.append(Spacer(1, 8))

    rows = [
        ("FULL LEGAL NAME",                                         legal_name),
        ("DATE OF BIRTH",                                            _format_dob(dob)),
        ("PLACE OF BIRTH",                                           place_of_birth),
        ("CURRENT RESIDENTIAL ADDRESS",                              f"{street_address}, {city_state_zip}"),
        ("IDENTIFICATION TYPE 1 — NUMBER",                           f"{id1_type} — {id1_number}" if id1_type else "—"),
        ("IDENTIFICATION TYPE 2 — NUMBER",                           f"{id2_type} — {id2_number}" if id2_type else "—"),
        ("TELEPHONE NUMBER",                                         phone),
        ("EMAIL ADDRESS",                                            email),
        ("ALL STAGE NAMES",                                          stage_names or talent_display),
        ("ALL PROFESSIONAL NAMES",                                   professional_names or "—"),
        ("ALL NICKNAMES AND ALIASES",                                nicknames_aliases or "—"),
        ("ANY OTHER NAMES (INCLUDING PREVIOUS LEGAL NAMES)",         previous_legal_names or "—"),
    ]
    out.append(_label_value_table(rows))
    out.append(Spacer(1, 10))

    out.append(Paragraph(_esc(cc.DOCUMENTS_PROVIDED_HEADING), _H2))
    for item in cc.DOCUMENTS_PROVIDED_LIST:
        out.append(Paragraph(_esc(item), _BODY))
    out.append(Spacer(1, 10))

    out.append(Paragraph(_esc(cc.DATA_CONSENT), _BODY))
    out.append(Spacer(1, 10))
    out.append(Paragraph(_esc(cc.PERJURY_STATEMENT), _BODY))
    out.append(Spacer(1, 8))
    out.append(Paragraph(_esc(cc.INDEMNITY_STATEMENT), _BODY))
    out.append(Spacer(1, 14))

    # Final perjury signature block
    out.append(_label_value_table([
        ("Dated",                  _long_date(shoot_date)),
        ("Printed Full Legal Name", legal_name),
        ("Date of Birth",           _format_dob(dob)),
    ]))
    out.append(Spacer(1, 4))
    out.append(_signature_only(signature_png_bytes))
    return out


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _label_value_table(rows: list[tuple[str, str]]) -> Table:
    data = [[Paragraph(_esc(lbl), _LABEL), Paragraph(_esc(val) or "—", _VALUE)] for lbl, val in rows]
    t = Table(data, colWidths=[2.2 * inch, 4.6 * inch])
    t.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    return t


def _signature_block(
    signature_png_bytes: bytes,
    legal_name: str,
    signed_at_iso: str,
    shoot_date: date,
) -> Table:
    """Sign-here block for the W-9 page."""
    sig = _signature_image(signature_png_bytes, max_width=2.6 * inch, max_height=0.6 * inch)
    data = [
        [Paragraph(_esc("Signature of U.S. person"), _LABEL),  Paragraph(_esc("Date"), _LABEL)],
        [sig,                                                  Paragraph(_esc(_long_date(shoot_date)), _VALUE)],
        [Paragraph(f"<b>{_esc(legal_name)}</b>", _VALUE),      Paragraph(_esc(_short_iso(signed_at_iso)), _VALUE)],
    ]
    t = Table(data, colWidths=[3.6 * inch, 3.0 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 1), (0, 1), 0.5, colors.black),
        ("LINEBELOW", (1, 1), (1, 1), 0.5, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _two_col_signatures(
    *,
    producer_name: str,
    legal_name: str,
    talent_display: str,
    signature_png_bytes: bytes,
    shoot_date: date,
) -> Table:
    """Producer | Model two-column signature footer for the agreement."""
    sig = _signature_image(signature_png_bytes, max_width=2.4 * inch, max_height=0.55 * inch)
    data = [
        [Paragraph("<b>PRODUCER:</b>", _LABEL), Paragraph("<b>MODEL:</b>", _LABEL)],
        [Paragraph(f"Name: {_esc(producer_name)}", _VALUE),
         Paragraph(f"Legal Name: <b>{_esc(legal_name)}</b>", _VALUE)],
        [Paragraph("Title: Producer", _VALUE),
         Paragraph(f"Stage Name: {_esc(talent_display)}", _VALUE)],
        [Paragraph("By: ____________________", _VALUE), sig],
        ["",
         Paragraph(f"Date: {_esc(_long_date(shoot_date))}", _VALUE)],
    ]
    t = Table(data, colWidths=[3.4 * inch, 3.4 * inch])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
    ]))
    return t


def _signature_only(signature_png_bytes: bytes) -> Table:
    """Just the signature row + label, used for the final perjury page."""
    sig = _signature_image(signature_png_bytes, max_width=3.6 * inch, max_height=0.7 * inch)
    data = [[Paragraph(_esc("Signature"), _LABEL)], [sig]]
    t = Table(data, colWidths=[6.8 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 1), (0, 1), 0.5, colors.black),
    ]))
    return t


def _signature_image(png_bytes: bytes, *, max_width: float, max_height: float) -> Image:
    """Build a Platypus Image from the PNG bytes, scaled to fit the box while keeping aspect."""
    img = Image(io.BytesIO(png_bytes))
    iw, ih = img.imageWidth, img.imageHeight
    if iw <= 0 or ih <= 0:
        img.drawWidth = max_width
        img.drawHeight = max_height
        return img
    scale = min(max_width / iw, max_height / ih)
    img.drawWidth  = iw * scale
    img.drawHeight = ih * scale
    return img


def _format_tin(tin: str, tin_type: str) -> str:
    """Render TIN as 'NNN-NN-NNNN' (SSN) or 'NN-NNNNNNN' (EIN)."""
    digits = "".join(c for c in tin if c.isdigit())
    if tin_type == "ssn" and len(digits) == 9:
        return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    if tin_type == "ein" and len(digits) == 9:
        return f"{digits[:2]}-{digits[2:]}"
    return tin or "—"


def _format_dob(dob_iso: str) -> str:
    try:
        from datetime import datetime
        d = datetime.strptime(dob_iso, "%Y-%m-%d")
    except Exception:
        return dob_iso or "—"
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")


def _long_date(d: date) -> str:
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")


def _short_iso(iso: str) -> str:
    """ '2026-04-27T18:32:00Z' → '2026-04-27 18:32 UTC'. """
    if not iso:
        return ""
    try:
        from datetime import datetime
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso


def _tax_class_label(tax_classification: str, llc_class: str, other_classification: str) -> str:
    base = {
        "individual":   "Individual / sole proprietor / single-member LLC",
        "c_corp":       "C Corporation",
        "s_corp":       "S Corporation",
        "partnership":  "Partnership",
        "trust_estate": "Trust / estate",
        "llc":          f"Limited liability company (tax class: {llc_class or '—'})",
        "other":        f"Other: {other_classification or '—'}",
    }.get(tax_classification, tax_classification or "—")
    return base
