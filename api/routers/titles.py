"""
Titles API router.

Provides AI-powered title card generation via fal.ai Ideogram V3
and local PIL-based model name card generation.

Routes:
  POST /api/titles/cloud      — generate title card image via fal.ai Ideogram V3
  POST /api/titles/model-name — generate model name PNG (VRA/VRH PIL renderer)
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from api.auth import CurrentUser
from api.config import get_settings

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/titles", tags=["titles"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

_STYLE_HINTS: dict[str, str] = {
    "cinematic": "dramatic cinematic style, dark moody atmosphere, film poster composition, deep shadows",
    "bold": "bold graphic design, high contrast, heavy display typography, editorial punch",
    "minimal": "minimal clean design, generous white space, elegant refined typography, restrained palette",
}

class TitleRequest(BaseModel):
    text: str
    style: str = "cinematic"        # "cinematic", "bold", "minimal"
    studio: str | None = None       # optional studio context for color hints
    n: int = 1                      # number of variations (1–4)


class TitleResponse(BaseModel):
    url: str | None
    error: str | None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

async def _generate_one(client: httpx.AsyncClient, fal_key: str, prompt: str) -> TitleResponse:
    """Run a single fal.ai Ideogram V3 request."""
    try:
        resp = await client.post(
            "https://fal.run/fal-ai/ideogram/v3",
            headers={"Authorization": f"Key {fal_key}"},
            json={"prompt": prompt, "style_type": "DESIGN"},
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        url = data.get("images", [{}])[0].get("url")
        return TitleResponse(url=url, error=None)
    except httpx.HTTPStatusError as exc:
        return TitleResponse(url=None, error=f"fal.ai error: {exc.response.status_code}")
    except Exception as exc:
        return TitleResponse(url=None, error=str(exc))


@router.post("/cloud", response_model=list[TitleResponse])
async def generate_cloud_title(body: TitleRequest, user: CurrentUser):
    """
    Generate title card image(s) via fal.ai Ideogram V3.

    With n=1 (default) returns a single-element list for backwards compat.
    With n=2–4 runs requests concurrently and returns all results.
    """
    import asyncio

    settings = get_settings()

    if not settings.fal_key:
        return [TitleResponse(url=None, error="FAL_KEY not configured")]

    n = max(1, min(4, body.n))
    style_hint = _STYLE_HINTS.get(body.style, _STYLE_HINTS["cinematic"])
    prompt = f"VR adult entertainment title card: {body.text}. {style_hint}."

    async with httpx.AsyncClient() as client:
        tasks = [_generate_one(client, settings.fal_key, prompt) for _ in range(n)]
        results = await asyncio.gather(*tasks)

    return list(results)


# ---------------------------------------------------------------------------
# Model Name Generator
# ---------------------------------------------------------------------------

class ModelNameRequest(BaseModel):
    name: str
    studio: str = "VRH"   # "VRA" or "VRH"


class ModelNameResponse(BaseModel):
    data_url: str   # data:image/png;base64,...
    error: str | None = None


@router.post("/model-name", response_model=ModelNameResponse)
async def generate_model_name(body: ModelNameRequest, user: CurrentUser):
    """
    Generate a styled model name PNG using the local PIL renderer (cta_generator).

    VRA — BebasNeue, cyan fill, white stroke, drop shadow, bevel
    VRH — Ethnocentric/Audiowide, teal fill, black stroke, bevel, inner glow

    Returns a base64 data URL for direct use in <img src="..."/>.
    """
    def _render() -> bytes:
        import sys
        import os
        # cta_generator lives in the project root (parent of api/)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from cta_generator import generate_model_name_png
        return generate_model_name_png(body.name.strip(), body.studio.upper())

    try:
        png_bytes = await asyncio.get_event_loop().run_in_executor(None, _render)
        b64 = base64.b64encode(png_bytes).decode()
        return ModelNameResponse(data_url=f"data:image/png;base64,{b64}")
    except Exception as exc:
        _log.exception("Model name render failed")
        return ModelNameResponse(data_url="", error=str(exc))
