"""
Generate the talent agreement PDF.

The W-9 page is the actual IRS Form W-9 — the same one the legacy Drive
templates used. We bundle it as api/templates/w9.pdf, fill its AcroForm
fields with the talent's W-9 data, and prepend it to our ReportLab-rendered
agreement so the final PDF is one continuous document the talent signs.

Output layout:
  Page 1     IRS Form W-9 (official, filled)
  Pages 2+   Model Services Agreement §§1–11 + witness + producer/model signatures
  Pages N+   18 U.S.C. § 2257 Performer Names Disclosure + perjury + indemnity + signature

Each section that requires a signature has an explicit "SIGNATURE FOR …"
header so the talent always knows which part of the contract their
signature attaches to.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import Optional

import pypdf
from pypdf.generic import NameObject, create_string_object

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.utils import ImageReader
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

W9_TEMPLATE = Path(__file__).parent / "templates" / "w9.pdf"


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
    tin: str,                        # raw digits
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
    """Render the agreement+disclosure pages, then prepend the filled IRS W-9
    so the final PDF is W-9 (official IRS form) + Model Services Agreement +
    2257 disclosure, all merged."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Build the ReportLab-rendered portion (agreement + disclosure)
    agreement_buf = io.BytesIO()
    _build_agreement_doc(
        agreement_buf,
        talent_display=talent_display,
        legal_name=legal_name,
        dob=dob,
        place_of_birth=place_of_birth,
        street_address=street_address,
        city_state_zip=city_state_zip,
        phone=phone,
        email=email,
        id1_type=id1_type, id1_number=id1_number,
        id2_type=id2_type, id2_number=id2_number,
        stage_names=stage_names,
        professional_names=professional_names,
        nicknames_aliases=nicknames_aliases,
        previous_legal_names=previous_legal_names,
        signature_png_bytes=signature_png_bytes,
        shoot_date=shoot_date,
        signed_at_iso=signed_at_iso,
    )
    agreement_buf.seek(0)

    # 2. Fill the IRS W-9 template (the actual government PDF, bundled in repo)
    w9_filled = _fill_w9(
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
        shoot_date=shoot_date,
    )

    # 3. Merge: W-9 (page 1) + agreement
    writer = pypdf.PdfWriter()
    writer.append(pypdf.PdfReader(io.BytesIO(w9_filled)))
    writer.append(pypdf.PdfReader(agreement_buf))
    with open(output_path, "wb") as f:
        writer.write(f)


def _build_agreement_doc(
    out_buf: io.BytesIO,
    *,
    talent_display: str,
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
    signature_png_bytes: bytes,
    shoot_date: date,
    signed_at_iso: str,
) -> None:
    """Render just the Model Services Agreement + 2257 Disclosure pages
    (everything that's NOT the W-9)."""
    doc = BaseDocTemplate(
        out_buf,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        title=f"{talent_display} — Eclatech Performer Agreement",
        author=cc.PRODUCER_NAME,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")

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
    story += _agreement_pages(
        talent_display=talent_display,
        legal_name=legal_name,
        signature_png_bytes=signature_png_bytes,
        shoot_date=shoot_date,
        signed_at_iso=signed_at_iso,
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
        id1_type=id1_type, id1_number=id1_number,
        id2_type=id2_type, id2_number=id2_number,
        stage_names=stage_names,
        professional_names=professional_names,
        nicknames_aliases=nicknames_aliases,
        previous_legal_names=previous_legal_names,
        talent_display=talent_display,
        signature_png_bytes=signature_png_bytes,
        shoot_date=shoot_date,
        signed_at_iso=signed_at_iso,
    )
    doc.build(story)


# ─── IRS W-9 fill ────────────────────────────────────────────────────────────
#
# Field mapping was reverse-engineered from the prefilled male templates
# (Mike Mancini / Jayden Marcos / Danny Steele). See
# /Users/andrewninn/Downloads/.../*.pdf — the templates use generic
# "Custom Field N" / "Custom Checkbox N" names. Only fields visible on
# page 1 of the bundled w9.pdf are filled; the rest of the AcroForm
# catalog is dangling references from the original 7-page document and
# is harmless.
_W9_TAX_CLASS_CHECKBOX = {
    "individual":   "Custom Checkbox 1",   # Mike/Jayden/Danny all set this for Individual/Sole Proprietor
    "c_corp":        "Custom Checkbox 2",
    "s_corp":        "Custom Checkbox 3",
    "partnership":   "Custom Checkbox 4",
    "trust_estate":  "Custom Checkbox 5",
    "llc":           "Custom Checkbox 6",
    "other":         "Custom Checkbox 7",
}


def _fill_w9(
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
    shoot_date: date,
) -> bytes:
    """Fill the bundled IRS W-9 template's AcroForm with the talent's data
    and stamp the signature image over the Part II signature line. Returns
    the filled PDF bytes."""
    if not W9_TEMPLATE.exists():
        raise FileNotFoundError(
            f"W-9 template missing at {W9_TEMPLATE} — repo asset is required"
        )
    reader = pypdf.PdfReader(str(W9_TEMPLATE))
    writer = pypdf.PdfWriter()
    writer.append(reader)

    fields = {
        "Custom Field 1":  legal_name,
        "Custom Field 2":  business_name,
        "Custom Field 3":  llc_class,                       # LLC tax class letter (C/S/P)
        "Custom Field 4":  other_classification,
        "Custom Field 5":  exempt_payee_code,
        "Custom Field 6":  fatca_code,
        "Custom Field 7":  street_address,
        "Custom Field 9":  city_state_zip,
        "Text Field 1":    "".join(c for c in tin or "" if c.isdigit()),
    }
    target_checkbox = _W9_TAX_CLASS_CHECKBOX.get(tax_classification, "")

    for page in writer.pages:
        if "/Annots" not in page:
            continue
        for annot_ref in page["/Annots"]:
            annot = annot_ref.get_object()
            name = str(annot.get("/T") or "")
            ftype = str(annot.get("/FT", ""))
            if ftype == "/Btn":
                # Tax-classification checkboxes: tick the one that matches
                if name == target_checkbox:
                    annot.update({
                        NameObject("/V"):  NameObject("/Yes"),
                        NameObject("/AS"): NameObject("/Yes"),
                    })
            elif ftype == "/Tx" and name in fields:
                annot.update({
                    NameObject("/V"):  create_string_object(fields[name]),
                    NameObject("/DV"): create_string_object(fields[name]),
                })

    # Stamp the signature image on top of the W-9 signature line. The legacy
    # template has "Signature 1" as a text field; we additionally draw the
    # PNG so the talent's drawn signature is visible.
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return _stamp_w9_signature(buf.getvalue(), signature_png_bytes, shoot_date)


def _stamp_w9_signature(
    pdf_bytes: bytes, signature_png_bytes: bytes, shoot_date: date,
) -> bytes:
    """Overlay the signature PNG and the date onto the W-9 Sign-Here block
    using a ReportLab canvas, then merge with the filled W-9."""
    from reportlab.pdfgen import canvas
    overlay_buf = io.BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=letter)
    # IRS W-9 (Rev. 10-2018) signature line sits in the lower-right of
    # page 1 in the "Sign Here" block. Coordinates are PDF points (1/72")
    # measured from bottom-left.
    sig_io = io.BytesIO(signature_png_bytes)
    c.drawImage(
        ImageReader(sig_io),
        x=2.85 * inch, y=2.50 * inch,
        width=2.5 * inch, height=0.45 * inch,
        mask="auto",
        preserveAspectRatio=True,
    )
    c.setFont("Helvetica", 10)
    c.drawString(5.7 * inch, 2.55 * inch, _long_date(shoot_date))
    c.save()
    overlay_buf.seek(0)

    base = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    overlay = pypdf.PdfReader(overlay_buf)
    out_writer = pypdf.PdfWriter()
    out_writer.append(base)
    out_writer.pages[0].merge_page(overlay.pages[0])
    out = io.BytesIO()
    out_writer.write(out)
    return out.getvalue()


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
_SECTION_SIG_HEADER = ParagraphStyle(
    "section_sig_header", parent=_BASE["Heading2"],
    fontName="Helvetica-Bold", fontSize=11, leading=14,
    spaceBefore=14, spaceAfter=4, alignment=TA_LEFT,
    textColor=colors.HexColor("#000000"),
    backColor=colors.HexColor("#FEF3C7"),
    borderPadding=6, borderColor=colors.HexColor("#92400E"),
    borderWidth=0.5,
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


def _agreement_pages(
    *,
    talent_display: str,
    legal_name: str,
    signature_png_bytes: bytes,
    shoot_date: date,
    signed_at_iso: str,
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

    # Explicit section signature: makes clear the talent's signature attaches
    # to sections 1–11 (the Model Services Agreement) and nothing else.
    out.append(Paragraph(
        _esc("SIGNATURE — MODEL SERVICES AGREEMENT (Sections 1–11 above)"),
        _SECTION_SIG_HEADER,
    ))
    out.append(Paragraph(
        _esc(
            f"By signing below, I, {legal_name}, agree to the Model Services "
            f"Agreement set out in Sections 1–11 above and acknowledge that I "
            f"have read, understood, and accept its terms."
        ),
        _BODY,
    ))
    out.append(Spacer(1, 6))
    out.append(_two_col_signatures(
        producer_name=cc.PRODUCER_NAME,
        legal_name=legal_name,
        talent_display=talent_display,
        signature_png_bytes=signature_png_bytes,
        shoot_date=shoot_date,
        signed_at_iso=signed_at_iso,
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
    signed_at_iso: str,
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

    # Explicit section signature: makes clear the talent's signature attaches
    # to the 18 U.S.C. § 2257 Performer Names Disclosure, the data-processing
    # consent, and the perjury + indemnity statements above.
    out.append(Paragraph(
        _esc("SIGNATURE — PERFORMER NAMES DISCLOSURE & PERJURY STATEMENT"),
        _SECTION_SIG_HEADER,
    ))
    out.append(Paragraph(
        _esc(
            f"By signing below, I, {legal_name}, swear under the pains and "
            f"penalties of perjury that the information given on the "
            f"Performer Names Disclosure above is true, correct, and complete; "
            f"that I am over eighteen (18) years of age (or the age of majority "
            f"in my legal jurisdiction); and I consent to the data processing "
            f"described above."
        ),
        _BODY,
    ))
    out.append(Spacer(1, 6))
    out.append(_label_value_table([
        ("Dated",                   _long_date(shoot_date)),
        ("Signed at (UTC)",          _short_iso(signed_at_iso)),
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


def _two_col_signatures(
    *,
    producer_name: str,
    legal_name: str,
    talent_display: str,
    signature_png_bytes: bytes,
    shoot_date: date,
    signed_at_iso: str,
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
        [Paragraph(f"Date: {_esc(_long_date(shoot_date))}", _VALUE),
         Paragraph(f"Signed (UTC): {_esc(_short_iso(signed_at_iso))}", _VALUE)],
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


