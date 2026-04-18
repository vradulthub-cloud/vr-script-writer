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

    n = max(1, min(20, body.n))
    style_hint = _STYLE_HINTS.get(body.style, _STYLE_HINTS["cinematic"])
    prompt = f"VR adult entertainment title card: {body.text}. {style_hint}."

    async with httpx.AsyncClient() as client:
        tasks = [_generate_one(client, settings.fal_key, prompt) for _ in range(n)]
        results = await asyncio.gather(*tasks)

    return list(results)


# ---------------------------------------------------------------------------
# Local PIL title generation (690+ treatments)
# ---------------------------------------------------------------------------

def _get_cta_module():
    """Lazy-import cta_generator from project root."""
    import sys
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    import cta_generator
    return cta_generator


class LocalTitleRequest(BaseModel):
    text: str
    treatments: list[str] | None = None   # specific treatment names; None = random
    n: int = 6                             # number of variations (1–12)
    seed: int = 0                          # 0 = random
    auto_match: bool = False               # pick treatment via cta.detect_treatment()


class LocalTitleResponse(BaseModel):
    data_url: str             # base64 PNG
    treatment_name: str
    error: str | None = None


@router.get("/treatments")
async def list_treatments(user: CurrentUser):
    """Return all available local PIL treatment names with featured flag."""
    try:
        cta = _get_cta_module()
        all_names = sorted(cta.TREATMENTS.keys())
        featured = set(getattr(cta, "FEATURED_TREATMENTS", {}).keys())
        return [
            {"name": name, "featured": name in featured}
            for name in all_names
        ]
    except Exception as exc:
        _log.exception("Failed to load treatments")
        return []


@router.post("/local", response_model=list[LocalTitleResponse])
async def generate_local_title(body: LocalTitleRequest, user: CurrentUser):
    """
    Generate title card PNG(s) using the local PIL renderer.

    With treatments=None, picks n random treatments.
    With treatments=[...], renders each specified treatment.
    """
    import random

    n = max(1, min(12, body.n))
    seed = body.seed if body.seed > 0 else random.randint(1, 999999)

    def _render():
        cta = _get_cta_module()
        treatments = cta.TREATMENTS

        # Pick which treatments to use
        if body.auto_match:
            # Keyword-score the title; render N variations of the best match
            try:
                best = cta.detect_treatment(body.text) if hasattr(cta, "detect_treatment") else None
            except Exception:  # pragma: no cover
                best = None
            if best and best in treatments:
                names = [best] * n
            else:
                # Fall back to random if detect_treatment isn't available
                all_names = list(treatments.keys())
                rng = random.Random(seed)
                names = rng.sample(all_names, min(n, len(all_names)))
        elif body.treatments:
            names = [t for t in body.treatments if t in treatments][:n]
        else:
            all_names = list(treatments.keys())
            rng = random.Random(seed)
            names = rng.sample(all_names, min(n, len(all_names)))

        results = []
        for i, name in enumerate(names):
            try:
                render_fn = treatments[name]
                img = render_fn(body.text, random.Random(seed + i * 1000))
                # Apply UnsharpMask for sharpness
                from PIL import ImageFilter
                img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=60))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                results.append(LocalTitleResponse(
                    data_url=f"data:image/png;base64,{b64}",
                    treatment_name=name,
                ))
            except Exception as exc:
                results.append(LocalTitleResponse(
                    data_url="",
                    treatment_name=name,
                    error=str(exc),
                ))
        return results

    try:
        return await asyncio.get_event_loop().run_in_executor(None, _render)
    except Exception as exc:
        _log.exception("Local title generation failed")
        return [LocalTitleResponse(data_url="", treatment_name="", error=str(exc))]


class RefineRequest(BaseModel):
    text: str
    treatment_name: str
    refine_prompt: str          # e.g. "make it gold", "darker", "glow"
    seed: int = 0


@router.post("/refine", response_model=LocalTitleResponse)
async def refine_title(body: RefineRequest, user: CurrentUser):
    """
    Refine a local title by re-rendering with a modified treatment.

    Uses Ollama (if available) to rewrite the treatment function,
    otherwise falls back to keyword-based adjustments.
    """
    import random

    seed = body.seed if body.seed > 0 else random.randint(1, 999999)

    def _render():
        cta = _get_cta_module()
        treatments = cta.TREATMENTS
        if body.treatment_name not in treatments:
            return LocalTitleResponse(data_url="", treatment_name=body.treatment_name, error="Treatment not found")

        # Simple keyword-based adjustment as fallback
        render_fn = treatments[body.treatment_name]
        try:
            img = render_fn(body.text, random.Random(seed))
            from PIL import ImageFilter, ImageEnhance
            img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=60))

            # Apply simple adjustments based on refine prompt
            prompt_lower = body.refine_prompt.lower()
            if "darker" in prompt_lower:
                img = ImageEnhance.Brightness(img).enhance(0.7)
            elif "brighter" in prompt_lower:
                img = ImageEnhance.Brightness(img).enhance(1.3)
            elif "vivid" in prompt_lower or "saturate" in prompt_lower:
                img = ImageEnhance.Color(img).enhance(1.5)
            elif "muted" in prompt_lower or "desaturate" in prompt_lower:
                img = ImageEnhance.Color(img).enhance(0.5)
            elif "sharp" in prompt_lower:
                img = img.filter(ImageFilter.UnsharpMask(radius=2.0, percent=100))

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            return LocalTitleResponse(
                data_url=f"data:image/png;base64,{b64}",
                treatment_name=body.treatment_name,
            )
        except Exception as exc:
            return LocalTitleResponse(data_url="", treatment_name=body.treatment_name, error=str(exc))

    try:
        return await asyncio.get_event_loop().run_in_executor(None, _render)
    except Exception as exc:
        _log.exception("Title refine failed")
        return LocalTitleResponse(data_url="", treatment_name=body.treatment_name, error=str(exc))


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
