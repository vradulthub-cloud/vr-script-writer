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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageTemplate,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors


def _HRule(color, thickness: float = 0.5, *,
           width: Optional[float] = None,
           space_before: float = 0, space_after: float = 0):
    """Thin horizontal accent rule. `width` in points (None → full content width)."""
    return HRFlowable(
        width=width if width is not None else "100%",
        thickness=thickness,
        color=color,
        spaceBefore=space_before,
        spaceAfter=space_after,
        hAlign="LEFT",
    )

from api import compliance_contract as cc

W9_TEMPLATE = Path(__file__).parent / "templates" / "w9.pdf"

# ─── Brand ───────────────────────────────────────────────────────────────────

BRAND_LIME    = colors.HexColor("#BED62F")      # Eclatech primary action
BRAND_INK     = colors.HexColor("#0A0A0A")      # near-black for body text
BRAND_GRAPH   = colors.HexColor("#3F3F46")      # zinc-700 for secondary
BRAND_MUTED   = colors.HexColor("#71717A")      # zinc-500 for captions
BRAND_FAINT   = colors.HexColor("#A1A1AA")      # zinc-400 for hairlines
BRAND_RULE    = colors.HexColor("#E4E4E7")      # zinc-200 for table rules
BRAND_TINT    = colors.HexColor("#FAFAFA")      # zinc-50 background tint


# ─── Font registration ───────────────────────────────────────────────────────

_FONTS_REGISTERED = False


def _register_fonts() -> None:
    """Register Inter (bundled OTF) so all our styles resolve.
    Falls back to Helvetica weights if a file is missing — keeps the
    generator runnable even if the OTF assets get lost."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    base = Path(__file__).parent / "fonts" / "Inter"
    weights = [
        ("Inter",          "Inter-Regular.ttf",  "Helvetica"),
        ("Inter-Light",    "Inter-Light.ttf",    "Helvetica"),
        ("Inter-Medium",   "Inter-Medium.ttf",   "Helvetica"),
        ("Inter-SemiBold", "Inter-SemiBold.ttf", "Helvetica-Bold"),
        ("Inter-Bold",     "Inter-Bold.ttf",     "Helvetica-Bold"),
        ("Inter-Italic",   "Inter-Italic.ttf",   "Helvetica-Oblique"),
    ]
    loaded: dict[str, str] = {}
    for name, fname, fallback in weights:
        path = base / fname
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                loaded[name] = name
                continue
            except Exception:
                pass
        loaded[name] = fallback

    # ReportLab's Paragraph parser uses ps2tt(fontName) to derive bold/italic
    # variants — populate one family entry per face (each face is its own
    # family so subsequent registrations don't clobber prior bold/italic
    # mappings).
    for face in ("Inter", "Inter-Light", "Inter-Medium", "Inter-SemiBold",
                 "Inter-Bold", "Inter-Italic"):
        pdfmetrics.registerFontFamily(
            face,
            normal=loaded[face], bold=loaded[face],
            italic=loaded[face], boldItalic=loaded[face],
        )
    # Plus a sane "Inter" family so <b>…</b> in body paragraphs picks up Bold.
    pdfmetrics.registerFontFamily(
        "Inter",
        normal=loaded["Inter"],
        bold=loaded["Inter-Bold"],
        italic=loaded["Inter-Italic"],
        boldItalic=loaded["Inter-Bold"],
    )

    _FONTS_REGISTERED = True


def _font(weight: str = "regular", italic: bool = False) -> str:
    if italic and weight == "regular":
        return "Inter-Italic"
    return {
        "light":    "Inter-Light",
        "regular":  "Inter",
        "medium":   "Inter-Medium",
        "semibold": "Inter-SemiBold",
        "bold":     "Inter-Bold",
    }.get(weight, "Inter")


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

    # 1. Build the ReportLab-rendered portion (cover + agreement + disclosure)
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

    # 3. Final layout: cover (page 1 of agreement_buf) + W-9 + rest of agreement
    agreement_reader = pypdf.PdfReader(agreement_buf)
    w9_reader = pypdf.PdfReader(io.BytesIO(w9_filled))
    writer = pypdf.PdfWriter()
    writer.add_page(agreement_reader.pages[0])    # cover
    for p in w9_reader.pages:
        writer.add_page(p)                          # IRS W-9
    for p in agreement_reader.pages[1:]:
        writer.add_page(p)                          # agreement + disclosure
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
    """Render: cover + Model Services Agreement + 2257 Disclosure
    (everything that's NOT the IRS W-9)."""
    margin_x = 0.95 * inch
    margin_top = 0.95 * inch
    margin_bot = 0.95 * inch

    doc = BaseDocTemplate(
        out_buf,
        pagesize=letter,
        leftMargin=margin_x,
        rightMargin=margin_x,
        topMargin=margin_top,
        bottomMargin=margin_bot,
        title=f"{talent_display} — Performer Agreement",
        author=cc.PRODUCER_NAME,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")

    def _chrome(canv, _doc):
        canv.saveState()
        # Top hairline
        canv.setStrokeColor(BRAND_RULE)
        canv.setLineWidth(0.5)
        y_top = letter[1] - 0.55 * inch
        canv.line(margin_x, y_top, letter[0] - margin_x, y_top)
        # Header text — running head, all-caps tracked
        canv.setFont(_font("semibold"), 7)
        canv.setFillColor(BRAND_MUTED)
        head = f"{cc.PRODUCER_NAME.upper()}  ·  PERFORMER AGREEMENT  ·  {talent_display.upper()}"
        canv.drawString(margin_x, y_top + 7, head)

        # Bottom hairline + footer
        y_bot = 0.55 * inch
        canv.setStrokeColor(BRAND_RULE)
        canv.line(margin_x, y_bot + 14, letter[0] - margin_x, y_bot + 14)
        canv.setFont(_font("medium"), 7)
        canv.setFillColor(BRAND_MUTED)
        canv.drawString(
            margin_x, y_bot,
            f"{shoot_date.isoformat()}  ·  signed digitally on iPad  ·  retained per 18 U.S.C. § 2257",
        )
        canv.drawRightString(
            letter[0] - margin_x, y_bot,
            f"PAGE {canv.getPageNumber()}",
        )
        canv.restoreState()

    doc.addPageTemplates([PageTemplate(id="default", frames=[frame], onPage=_chrome)])

    story: list = []
    story += _cover_page(
        talent_display=talent_display,
        legal_name=legal_name,
        shoot_date=shoot_date,
    )
    story.append(PageBreak())
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
    # IRS W-9 (Rev. 10-2018) Sign Here block: the form's "Signature 1"
    # AcroForm field is at rect (121.9, 231.6) → (373.3, 253.7) in PDF
    # points — i.e. (1.69, 3.22) → (5.18, 3.52) in inches. The Date line
    # to its right has no form field; we draw the date manually next to
    # the signature line. PDF origin is bottom-left.
    sig_io = io.BytesIO(signature_png_bytes)
    c.drawImage(
        ImageReader(sig_io),
        x=1.75 * inch, y=3.18 * inch,
        width=3.40 * inch, height=0.40 * inch,
        mask="auto",
        preserveAspectRatio=True,
    )
    c.setFont("Helvetica", 11)
    c.drawString(5.55 * inch, 3.32 * inch, _long_date(shoot_date))
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


_register_fonts()
_BASE = getSampleStyleSheet()

# Display styles for the cover page
_DISPLAY = ParagraphStyle(
    "display", parent=_BASE["Heading1"],
    fontName=_font("bold"), fontSize=34, leading=38,
    textColor=BRAND_INK, spaceBefore=0, spaceAfter=4, alignment=TA_LEFT,
)
_DISPLAY_SUB = ParagraphStyle(
    "display_sub", parent=_BASE["BodyText"],
    fontName=_font("light"), fontSize=14, leading=20,
    textColor=BRAND_GRAPH, spaceBefore=0, spaceAfter=0, alignment=TA_LEFT,
)

# Eyebrow — small caps marker above headings, brand lime
_EYEBROW = ParagraphStyle(
    "eyebrow", parent=_BASE["BodyText"],
    fontName=_font("semibold"), fontSize=8, leading=12,
    textColor=BRAND_INK, spaceBefore=0, spaceAfter=4,
    alignment=TA_LEFT,
)

# Section header (replaces black banner) — large heading with a thin lime
# rule above and a subtle preamble below.
_SECTION_HEADING = ParagraphStyle(
    "section_heading", parent=_BASE["Heading1"],
    fontName=_font("bold"), fontSize=20, leading=24,
    textColor=BRAND_INK, spaceBefore=0, spaceAfter=2,
    alignment=TA_LEFT,
)
_SECTION_PREAMBLE = ParagraphStyle(
    "section_preamble", parent=_BASE["BodyText"],
    fontName=_font("regular"), fontSize=10, leading=15,
    textColor=BRAND_GRAPH, spaceBefore=4, spaceAfter=12,
    alignment=TA_LEFT,
)

# In-section headings
_H1 = ParagraphStyle(
    "h1", parent=_BASE["Heading1"],
    fontName=_font("semibold"), fontSize=14, leading=20,
    textColor=BRAND_INK, spaceBefore=12, spaceAfter=6, alignment=TA_LEFT,
)
_H2 = ParagraphStyle(
    "h2", parent=_BASE["Heading2"],
    fontName=_font("semibold"), fontSize=10.5, leading=16,
    textColor=BRAND_INK, spaceBefore=10, spaceAfter=2, alignment=TA_LEFT,
)
_BODY = ParagraphStyle(
    "body", parent=_BASE["BodyText"],
    fontName=_font("regular"), fontSize=9.5, leading=14,
    textColor=BRAND_INK, spaceBefore=0, spaceAfter=8,
    alignment=TA_JUSTIFY,
)
_BODY_SECONDARY = ParagraphStyle(
    "body_secondary", parent=_BODY,
    textColor=BRAND_GRAPH,
)

# Labels + values for performer-disclosure tables
_LABEL = ParagraphStyle(
    "label", parent=_BASE["BodyText"],
    fontName=_font("semibold"), fontSize=7.5, leading=11,
    textColor=BRAND_MUTED, spaceBefore=0, spaceAfter=0,
)
_VALUE = ParagraphStyle(
    "value", parent=_BASE["BodyText"],
    fontName=_font("medium"), fontSize=10.5, leading=14,
    textColor=BRAND_INK, spaceBefore=2, spaceAfter=0,
)

# Section signature (acknowledgement card before each signature block)
_SECTION_SIG_HEADER = ParagraphStyle(
    "section_sig_header", parent=_BASE["BodyText"],
    fontName=_font("semibold"), fontSize=8, leading=12,
    textColor=BRAND_INK, spaceBefore=0, spaceAfter=6,
    alignment=TA_LEFT,
)
_SECTION_SIG_BODY = ParagraphStyle(
    "section_sig_body", parent=_BASE["BodyText"],
    fontName=_font("regular"), fontSize=10, leading=15,
    textColor=BRAND_INK, spaceBefore=0, spaceAfter=8,
    alignment=TA_LEFT,
)

_FOOTER = ParagraphStyle(
    "footer", parent=_BASE["BodyText"],
    fontName=_font("medium"), fontSize=7, leading=9,
    textColor=BRAND_MUTED, alignment=TA_LEFT,
)
_FOOTER_RIGHT = ParagraphStyle(
    "footer_right", parent=_FOOTER, alignment=TA_LEFT,
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


def _section_marker(eyebrow: str, heading: str, preamble: str) -> list:
    """Eyebrow (small caps + lime rule) → heading → preamble.
    Replaces the old heavy black banner."""
    out: list = []
    # Lime accent rule on top
    out.append(_HRule(BRAND_LIME, 1.5, width=1.0 * inch, space_before=0, space_after=8))
    out.append(Paragraph(_esc(eyebrow.upper()), _EYEBROW))
    out.append(Paragraph(_esc(heading), _SECTION_HEADING))
    if preamble:
        out.append(Paragraph(_esc(preamble), _SECTION_PREAMBLE))
    return out


def _cover_page(
    *,
    talent_display: str,
    legal_name: str,
    shoot_date: date,
) -> list:
    """Cover page — sets the tone before the W-9."""
    out: list = []
    out.append(Spacer(1, 0.6 * inch))
    out.append(_HRule(BRAND_LIME, 2, width=0.8 * inch, space_before=0, space_after=20))
    out.append(Paragraph("PERFORMER AGREEMENT", _EYEBROW))
    out.append(Paragraph(_esc(talent_display), _DISPLAY))
    out.append(Paragraph(
        _esc(f"Performer agreement for the production dated {_long_date(shoot_date)}, "
             f"between {cc.PRODUCER_NAME} (Producer) and {legal_name} (Model)."),
        _DISPLAY_SUB,
    ))
    out.append(Spacer(1, 0.55 * inch))

    # "What's in this document" — 3 sections at a glance
    rows = [
        ("01", "IRS FORM W-9",
         "Taxpayer Identification Number and Certification. Required so the "
         "Producer can issue a 1099 at year end."),
        ("02", "MODEL SERVICES AGREEMENT",
         "Eleven sections covering services, compensation, grants of rights, "
         "confidentiality, testing, independent-contractor status, governing "
         "law and arbitration."),
        ("03", "18 U.S.C. § 2257 RECORDS",
         "Federal Performer Identification record. Names, aliases, "
         "government-issued ID details, and the perjury affirmation required "
         "by law."),
    ]
    out.append(_section_index_table(rows))

    # Footer block on cover — what to expect
    out.append(Spacer(1, 0.55 * inch))
    out.append(_HRule(BRAND_RULE, 0.5, width=None, space_before=0, space_after=10))
    out.append(Paragraph(
        _esc(
            "Each section is signed independently. Your signature on a section "
            "applies only to that section. Take your time, and ask the director "
            "anything you don't understand before signing."
        ),
        _BODY_SECONDARY,
    ))
    return out


def _section_index_table(rows: list[tuple[str, str, str]]) -> Table:
    """Three-column index card on the cover. Number | Title | Description."""
    style = TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.5, BRAND_RULE),
        ("LINEABOVE",     (0, 0), (-1,  0), 0.5, BRAND_RULE),
    ])
    num_style = ParagraphStyle(
        "idx_num", parent=_BASE["BodyText"],
        fontName=_font("light"), fontSize=22, leading=26,
        textColor=BRAND_LIME,
    )
    title_style = ParagraphStyle(
        "idx_title", parent=_BASE["BodyText"],
        fontName=_font("semibold"), fontSize=11, leading=14,
        textColor=BRAND_INK, spaceAfter=4,
    )
    desc_style = ParagraphStyle(
        "idx_desc", parent=_BASE["BodyText"],
        fontName=_font("regular"), fontSize=9, leading=13,
        textColor=BRAND_GRAPH,
    )
    data = []
    for num, title, desc in rows:
        title_p = Paragraph(_esc(title), title_style)
        desc_p  = Paragraph(_esc(desc), desc_style)
        cell = Table(
            [[title_p], [desc_p]],
            colWidths=[None],
            style=TableStyle([
                ("LEFTPADDING",  (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING",   (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
            ]),
        )
        data.append([Paragraph(num, num_style), cell])
    t = Table(data, colWidths=[0.7 * inch, 5.8 * inch])
    t.setStyle(style)
    return t


def _agreement_pages(
    *,
    talent_display: str,
    legal_name: str,
    signature_png_bytes: bytes,
    shoot_date: date,
    signed_at_iso: str,
) -> list:
    out: list = []
    out += _section_marker(
        eyebrow="SECTION 02 OF 03",
        heading="Model Services Agreement & Release",
        preamble=(
            "Sections 1–11 below set out your services, compensation, the rights "
            "you grant the Producer, confidentiality, testing, your status as an "
            "independent contractor, and governing law. Your signature at the end "
            "of this section applies only to Sections 1–11."
        ),
    )
    out.append(Paragraph(_esc(cc.CONTRACT_INTRO), _BODY))
    out.append(Spacer(1, 4))

    for sec in cc.AGREEMENT_SECTIONS:
        out.append(Paragraph(_esc(sec.heading), _H2))
        for para in sec.body.split("\n\n"):
            out.append(Paragraph(_esc(para), _BODY))

    out.append(Spacer(1, 6))
    out.append(Paragraph(_esc(cc.WITNESS_STATEMENT), _BODY))
    out.append(Paragraph(_esc(cc.EXECUTION_LINE), _BODY_SECONDARY))
    out.append(Spacer(1, 18))
    out.append(_acknowledgement_card(
        eyebrow="SIGNATURE OF MODEL  ·  SECTION 02 OF 03",
        body=(
            f"By signing below, I, {legal_name}, agree to the Model Services "
            f"Agreement set out in Sections 1–11 above and acknowledge that I "
            f"have read, understood, and accept its terms."
        ),
    ))
    out.append(Spacer(1, 8))
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
    out += _section_marker(
        eyebrow="SECTION 03 OF 03  ·  18 U.S.C. § 2257 RECORDS",
        heading="Performer Names Disclosure",
        preamble=(
            "This section is the federally-required Performer Identification "
            "record under 18 U.S.C. § 2257 and 28 C.F.R. § 75. The Producer is "
            "legally required to verify and retain identification information "
            "and a record of all names and aliases used by every performer in a "
            "sexually-explicit production. By completing and signing this "
            "section you provide the Producer with that record. Your signature "
            "at the end of this section applies only to the 2257 disclosure, "
            "the data-processing consent, and the perjury and indemnity "
            "statements below."
        ),
    )
    out.append(Paragraph(
        f"<b>Production:</b> {_esc(cc.PRODUCER_NAME)} studio production · "
        f"<b>Date:</b> {_esc(_long_date(shoot_date))}",
        _BODY_SECONDARY,
    ))
    out.append(Paragraph(
        f"I, <b>{_esc(legal_name)}</b>, " + _esc(cc.DISCLOSURE_STATEMENT.lstrip("I ")),
        _BODY,
    ))
    out.append(Spacer(1, 6))

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
    out.append(Spacer(1, 6))
    out.append(Paragraph(_esc(cc.INDEMNITY_STATEMENT), _BODY))
    out.append(Spacer(1, 18))
    out.append(_acknowledgement_card(
        eyebrow="SIGNATURE OF MODEL  ·  SECTION 03 OF 03",
        body=(
            f"By signing below, I, {legal_name}, swear under the pains and "
            f"penalties of perjury that the information given on the Performer "
            f"Names Disclosure above is true, correct, and complete; that I am "
            f"over eighteen (18) years of age (or the age of majority in my "
            f"legal jurisdiction); and I consent to the data processing described "
            f"above."
        ),
    ))
    out.append(Spacer(1, 8))
    out.append(_label_value_table([
        ("Dated",                   _long_date(shoot_date)),
        ("Signed at (UTC)",          _short_iso(signed_at_iso)),
        ("Printed Full Legal Name", legal_name),
        ("Date of Birth",           _format_dob(dob)),
    ]))
    out.append(Spacer(1, 6))
    out.append(_signature_only(signature_png_bytes))
    return out


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _label_value_table(rows: list[tuple[str, str]]) -> Table:
    """Two-column data table — label stacked above value in each cell, in
    pairs. Used for the 2257 disclosure data and the perjury sign-here block.
    """
    # Build a flat list of [label, value] pairs and arrange them into a
    # 2-column grid. Each grid cell stacks LABEL (small caps) atop VALUE.
    paired: list[list] = []
    bag = list(rows)
    while bag:
        left = bag.pop(0)
        right = bag.pop(0) if bag else ("", "")
        l_lbl, l_val = left
        r_lbl, r_val = right
        paired.append([
            Paragraph(_esc(l_lbl.upper()), _LABEL),
            Paragraph(_esc(r_lbl.upper()), _LABEL),
        ])
        paired.append([
            Paragraph(_esc(l_val) or "—", _VALUE),
            Paragraph(_esc(r_val) or "—", _VALUE),
        ])

    t = Table(paired, colWidths=[3.3 * inch, 3.3 * inch])
    style_cmds = [
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]
    # Add hairline between every label/value group (every 2 rows)
    for i in range(0, len(paired), 2):
        # Top space before label row
        style_cmds.append(("TOPPADDING",    (0, i),     (-1, i),     12))
        style_cmds.append(("BOTTOMPADDING", (0, i),     (-1, i),     2))
        # Value row spacing
        style_cmds.append(("TOPPADDING",    (0, i + 1), (-1, i + 1), 0))
        style_cmds.append(("BOTTOMPADDING", (0, i + 1), (-1, i + 1), 12))
        # Hairline above each group except the first
        if i > 0:
            style_cmds.append(("LINEABOVE", (0, i), (-1, i), 0.5, BRAND_RULE))
    # Top + bottom rules around the whole block
    style_cmds.append(("LINEABOVE", (0, 0), (-1, 0), 0.75, BRAND_INK))
    style_cmds.append(("LINEBELOW", (0, -1), (-1, -1), 0.75, BRAND_INK))

    t.setStyle(TableStyle(style_cmds))
    return t


def _acknowledgement_card(eyebrow: str, body: str) -> Table:
    """Sign-here acknowledgement: thin lime rule on the left edge, eyebrow,
    body. Replaces the old yellow-highlighted block."""
    inner = Table(
        [
            [Paragraph(_esc(eyebrow), _SECTION_SIG_HEADER)],
            [Paragraph(_esc(body), _SECTION_SIG_BODY)],
        ],
        colWidths=[None],
        style=TableStyle([
            ("LEFTPADDING",  (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING",   (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 12),
            ("BACKGROUND",   (0, 0), (-1, -1), BRAND_TINT),
            ("LINEBEFORE",   (0, 0), (0, -1),  3,   BRAND_LIME),
        ]),
    )
    return inner


def _two_col_signatures(
    *,
    producer_name: str,
    legal_name: str,
    talent_display: str,
    signature_png_bytes: bytes,
    shoot_date: date,
    signed_at_iso: str,
) -> Table:
    """Producer | Model two-column signature footer.
    Each column is: eyebrow → fields stacked → signature line → caption."""
    sig = _signature_image(signature_png_bytes, max_width=2.6 * inch, max_height=0.55 * inch)

    producer_col = Table(
        [
            [Paragraph(_esc("PRODUCER"), _LABEL)],
            [Paragraph(_esc(producer_name), _VALUE)],
            [Paragraph(_esc("Title · Producer"), _BODY_SECONDARY)],
            [Spacer(1, 0.55 * inch)],
            [Paragraph(_esc("Authorized signatory on file"), _BODY_SECONDARY)],
            [Paragraph(_esc(f"Date · {_long_date(shoot_date)}"), _BODY_SECONDARY)],
        ],
        colWidths=[None],
        style=TableStyle([
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("LINEBELOW",    (0, 3), (0, 3), 0.75, BRAND_INK),
        ]),
    )

    model_col = Table(
        [
            [Paragraph(_esc("MODEL"), _LABEL)],
            [Paragraph(_esc(legal_name), _VALUE)],
            [Paragraph(_esc(f"Stage name · {talent_display}"), _BODY_SECONDARY)],
            [sig],
            [Paragraph(_esc("Talent signature"), _BODY_SECONDARY)],
            [Paragraph(_esc(f"Date · {_long_date(shoot_date)}  ·  {_short_iso(signed_at_iso)}"), _BODY_SECONDARY)],
        ],
        colWidths=[None],
        style=TableStyle([
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("LINEBELOW",    (0, 3), (0, 3), 0.75, BRAND_INK),
            ("ALIGN",        (0, 3), (0, 3), "LEFT"),
        ]),
    )

    t = Table([[producer_col, model_col]], colWidths=[3.15 * inch, 3.45 * inch])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (0, 0), 32),
        ("RIGHTPADDING",  (1, 0), (1, 0), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _signature_only(signature_png_bytes: bytes) -> Table:
    """Single signature line, used for the final perjury page."""
    sig = _signature_image(signature_png_bytes, max_width=3.8 * inch, max_height=0.65 * inch)
    data = [
        [Paragraph(_esc("MODEL SIGNATURE"), _LABEL)],
        [sig],
        [Paragraph(_esc("Drawn on iPad — captured digitally"), _BODY_SECONDARY)],
    ]
    t = Table(data, colWidths=[6.6 * inch])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW",     (0, 1), (0, 1), 0.75, BRAND_INK),
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


