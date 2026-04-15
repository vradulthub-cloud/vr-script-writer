"""
Descriptions API router.

Provides streaming SSE endpoint for AI scene description generation
and a save endpoint to persist generated descriptions.

Routes:
  POST /api/descriptions/generate — streaming SSE description generation
  POST /api/descriptions/save     — save description to SQLite scenes table
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import anthropic
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import CurrentUser
from api.config import get_settings
from api.database import get_db
from api.prompts import DESC_SYSTEMS, DESC_COMPILATION_SYSTEMS, STUDIO_KEY_MAP

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/descriptions", tags=["descriptions"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class DescGenRequest(BaseModel):
    studio: str                     # "FuckPassVR", "VRHush", "VRAllure", "NaughtyJOI"
    scene_id: str | None = None
    is_compilation: bool = False
    performers: str = ""
    sex_positions: str = ""
    categories: str = ""
    target_keywords: str = ""
    wardrobe: str = ""
    model_properties: str = ""      # freeform model notes
    plot: str = ""                  # existing plot for context


class DescSaveBody(BaseModel):
    scene_id: str
    description: str
    meta_title: str | None = None
    meta_description: str | None = None


class SeoGenRequest(BaseModel):
    description: str
    studio: str
    performers: str = ""
    title: str = ""


class DocxRequest(BaseModel):
    description: str
    title: str = ""
    meta_title: str | None = None
    meta_description: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_description(body: DescGenRequest, user: CurrentUser):
    """
    Generate a scene description via Claude (streaming SSE).

    Uses per-studio system prompts. Compilation scenes use the
    DESC_COMPILATION_SYSTEMS prompts; regular scenes use DESC_SYSTEMS.
    """
    studio_key = STUDIO_KEY_MAP.get(body.studio)
    if not studio_key:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown studio: {body.studio}. Must be one of: {', '.join(STUDIO_KEY_MAP.keys())}",
        )

    prompt_dict = DESC_COMPILATION_SYSTEMS if body.is_compilation else DESC_SYSTEMS
    system_prompt = prompt_dict.get(studio_key)
    if not system_prompt:
        raise HTTPException(
            status_code=400,
            detail=f"No description prompt found for studio key: {studio_key}",
        )

    user_prompt = _build_desc_user_prompt(body)
    settings = get_settings()

    def event_stream():
        try:
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'text', 'text': text})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            _log.error("Description generation failed: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/seo")
async def generate_seo_tags(body: SeoGenRequest, user: CurrentUser):
    """
    Generate SEO meta title and meta description for a scene.

    Returns plain JSON (not streaming) — fast single-call Claude response.
    """
    settings = get_settings()

    system_prompt = (
        "You are an SEO specialist for adult VR content. Given a scene description, "
        "generate two fields and return ONLY valid JSON — no markdown, no commentary:\n"
        "- meta_title: A keyword-rich title under 60 characters. Include studio name and key performer/act.\n"
        "- meta_description: Under 155 characters. Punchy, includes performer name, key act, light CTA.\n"
        "Return exactly: {\"meta_title\": \"...\", \"meta_description\": \"...\"}"
    )

    user_parts = [f"Studio: {body.studio}"]
    if body.performers:
        user_parts.append(f"Performers: {body.performers}")
    if body.title:
        user_parts.append(f"Scene title: {body.title}")
    user_parts.append(f"\nDescription:\n{body.description[:1000]}")
    user_prompt = "\n".join(user_parts)

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        import json as _json
        raw = msg.content[0].text.strip()
        # Strip any markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        data = _json.loads(raw)
        return {
            "meta_title": str(data.get("meta_title", ""))[:60],
            "meta_description": str(data.get("meta_description", ""))[:155],
        }
    except Exception as exc:
        _log.error("SEO generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/docx")
async def download_description_docx(body: DocxRequest, user: CurrentUser):
    """
    Generate and return a DOCX file containing the scene description.

    Includes meta title and meta description if provided.
    """
    from io import BytesIO
    from docx import Document
    from docx.shared import Pt, RGBColor
    from fastapi.responses import Response

    doc = Document()

    # Title (if provided)
    if body.title:
        h = doc.add_heading(body.title, level=1)
        h.runs[0].font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)

    # Main description — split on double newlines into paragraphs
    paragraphs = [p.strip() for p in body.description.split("\n\n") if p.strip()]
    for para_text in paragraphs:
        p = doc.add_paragraph(para_text)
        p.runs[0].font.size = Pt(11)

    # SEO section
    if body.meta_title or body.meta_description:
        doc.add_paragraph("")  # spacer
        doc.add_heading("SEO Metadata", level=2)
        if body.meta_title:
            p = doc.add_paragraph()
            p.add_run("Meta Title: ").bold = True
            p.add_run(body.meta_title)
        if body.meta_description:
            p = doc.add_paragraph()
            p.add_run("Meta Description: ").bold = True
            p.add_run(body.meta_description)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    filename = "description.docx"
    if body.title:
        safe = body.title[:40].replace(" ", "_").replace("/", "-")
        filename = f"{safe}.docx"

    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/save")
async def save_description(body: DescSaveBody, user: CurrentUser):
    """
    Save a description to the SQLite scenes table.

    Note: Grail write-through (for the actual site) goes through the
    approvals flow, not directly here.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM scenes WHERE id = ?", (body.scene_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Scene not found")

        conn.execute(
            "UPDATE scenes SET has_description=1 WHERE id=?",
            (body.scene_id,),
        )

    return {"scene_id": body.scene_id, "status": "saved"}


# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------

def _build_desc_user_prompt(body: DescGenRequest) -> str:
    """Build the user-turn prompt for description generation."""
    lines = [f"Write a scene description for {body.studio} with the following details:"]

    if body.performers:
        lines.append(f"Performers: {body.performers}")
    if body.sex_positions:
        lines.append(f"Sex Positions: {body.sex_positions}")
    if body.categories:
        lines.append(f"Categories: {body.categories}")
    if body.target_keywords:
        lines.append(f"Target Keywords: {body.target_keywords}")
    if body.wardrobe:
        lines.append(f"Wardrobe: {body.wardrobe}")
    if body.model_properties:
        lines.append(f"Model Notes: {body.model_properties}")
    if body.plot:
        lines.append(f"Plot Summary: {body.plot}")

    return "\n".join(lines)
