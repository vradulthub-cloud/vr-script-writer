"""
Titles API router.

Local-only title PNG generation. Two pipelines:

  POST /api/titles/local        — render via PIL treatment library (700+ themes)
  POST /api/titles/flux-local   — render via ComfyUI on Windows box (FLUX.1 Schnell + RMBG-2.0)
  POST /api/titles/refine       — re-render an existing local title with adjustments
  POST /api/titles/model-name   — render model name PNG (VRA/VRH PIL renderer)
  GET  /api/titles/treatments   — list available PIL treatments
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import uuid
from pathlib import Path
from typing import Literal, TypedDict

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from api.auth import CurrentUser
from api.config import get_settings

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/titles", tags=["titles"])


# ---------------------------------------------------------------------------
# Local PIL title generation (700+ treatments)
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

    base_seed = body.seed if body.seed > 0 else random.randint(1, 999999)
    # Mix the refine prompt into the seed so re-rendering actually varies the
    # composition (different palette samples, different stochastic effects)
    # rather than just applying post-processing to the original render.
    import hashlib as _hashlib
    prompt_hash = int(_hashlib.md5(body.refine_prompt.encode()).hexdigest(), 16) % (2**31)
    seed = (base_seed + prompt_hash) % (2**31)

    def _render():
        cta = _get_cta_module()
        treatments = cta.TREATMENTS
        if body.treatment_name not in treatments:
            return LocalTitleResponse(data_url="", treatment_name=body.treatment_name, error="Treatment not found")

        render_fn = treatments[body.treatment_name]
        try:
            img = render_fn(body.text, random.Random(seed))
            from PIL import ImageFilter, ImageEnhance
            img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=60))

            # Apply intent-driven adjustments on top of the re-rendered image.
            # Layered with the seed-jitter above, the refine result both varies
            # (new draw) AND honors the explicit color/brightness intent.
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


# ---------------------------------------------------------------------------
# Local AI generation — ComfyUI (FLUX.1 Schnell + RMBG-2.0) on Windows box
# ---------------------------------------------------------------------------

_FLUX_TITLE_LORA = "title_card_style_v2-final.safetensors"
_WORKFLOW_PATH = Path(__file__).resolve().parent.parent / "workflows" / "flux_transparent_title.json"

# Photographic material styles. Each entry is a prompt fragment that fills
# {text} with the title and produces a distinct visual treatment FLUX can
# render but PIL fundamentally cannot — real metallic reflections, marble
# veining, holographic chromatic shift, etc. Six curated styles cover the
# range from premium-classical to retro-futurist without overlapping.
#
# Common scaffolding (white background, no decorations, single line, sharp
# letterforms) is appended to every prompt so RMBG can cleanly extract the
# foreground regardless of style.
FluxStyle = Literal[
    "gold-leaf",
    "chrome",
    "marble",
    "vintage-film",
    "holographic",
    "brushed-steel",
    "trained-style",
]


class _StyleConfig(TypedDict):
    """Per-style render config. The prompt fragment fills {text} with the
    title; lora_default decides whether the style needs the trained LoRA
    by default (overridable per-request); enabled gates the style behind
    a settings flag so unconverged work isn't user-visible.
    """
    label: str
    prompt: str
    lora_default: bool
    lora_strength: float
    enabled: Literal["always"] | str  # "always" or a settings.* attribute name


# Six photographic-material styles + one LoRA-driven preset. Photographic
# styles describe the surface FLUX should render directly. The trained-style
# preset hands styling over to the title_card_style_v2 LoRA — its prompt is
# deliberately neutral so the LoRA can dominate without being overruled by
# competing material descriptors.
_FLUX_STYLES: dict[str, _StyleConfig] = {
    "gold-leaf": {
        "label": "Gold leaf",
        "prompt": (
            "the words \"{text}\" rendered as bold metallic gold typography, "
            "photographic gold leaf material with subtle imperfections and warm highlights"
        ),
        "lora_default": False,
        "lora_strength": 0.0,
        "enabled": "always",
    },
    "chrome": {
        "label": "Chrome",
        "prompt": (
            "the words \"{text}\" rendered as polished chrome typography, "
            "mirror-like reflective metal with sharp specular highlights and cool blue undertones"
        ),
        "lora_default": False,
        "lora_strength": 0.0,
        "enabled": "always",
    },
    "marble": {
        "label": "Marble",
        "prompt": (
            "the words \"{text}\" rendered as carved white marble typography, "
            "natural stone with delicate gold veining, soft diffuse lighting, classical cut letterforms"
        ),
        "lora_default": False,
        "lora_strength": 0.0,
        "enabled": "always",
    },
    "vintage-film": {
        "label": "Vintage film",
        "prompt": (
            "the words \"{text}\" rendered as warm vintage film typography, "
            "celluloid grain texture, faded amber and cream tones, soft edge bleed, 1970s movie title aesthetic"
        ),
        "lora_default": False,
        "lora_strength": 0.0,
        "enabled": "always",
    },
    "holographic": {
        "label": "Holographic",
        "prompt": (
            "the words \"{text}\" rendered as iridescent holographic foil typography, "
            "prismatic chromatic shift across surface, magenta-cyan-yellow shimmer, glossy reflective material"
        ),
        "lora_default": False,
        "lora_strength": 0.0,
        "enabled": "always",
    },
    "brushed-steel": {
        "label": "Brushed steel",
        "prompt": (
            "the words \"{text}\" rendered as brushed stainless steel typography, "
            "directional micro-striations along grain, matte industrial finish, neutral gray tones"
        ),
        "lora_default": False,
        "lora_strength": 0.0,
        "enabled": "always",
    },
    "trained-style": {
        "label": "Trained style",
        # Neutral prompt — let the LoRA's learned style do the talking. Any
        # specific material descriptor here would compete with the LoRA and
        # produce muddy output. Strength is read from settings, not baked
        # in, so the threshold can be tuned without redeploys.
        "prompt": (
            "the words \"{text}\" rendered as bold display typography, "
            "high-quality movie title card design"
        ),
        "lora_default": True,
        "lora_strength": 0.0,  # filled from settings.flux_trained_lora_strength at build time
        "enabled": "flux_trained_style_enabled",
    },
}

_FLUX_PROMPT_SUFFIX = (
    ", isolated text only on pure white background, no decorations, no frame, "
    "no border, no panels, no objects, centered display lettering, "
    "sharp clean letterforms, single line of text"
)


class FluxLocalRequest(BaseModel):
    text: str
    # Visual style preset. Each maps to a curated prompt prefix optimised for
    # FLUX.1 Schnell + RMBG-2.0. PIL's 700+ treatments cover procedural
    # effects; FLUX styles cover photographic materials PIL can't render.
    # The "trained-style" preset hands styling to the title_card_style_v2
    # LoRA — the style itself decides whether LoRA is used and at what
    # strength, so callers don't need to think about it.
    style: FluxStyle = "gold-leaf"
    # LoRA override. None = trust the style's `lora_default`. True/False
    # forces LoRA on/off regardless of style. Power-user / debug knob;
    # the dropdown UI normally leaves this None.
    use_lora: bool | None = None
    steps: int = 6                                        # 4 = fast but drops letters, 6-8 = clean spelling
    seed: int = 0                                         # 0 = random
    width: int = 1024                                     # multiple of 64
    height: int = 512                                     # multiple of 64
    bg_remove: Literal["rmbg2", "none"] = "rmbg2"         # extract alpha (rmbg2) or pass-through


class FluxLocalResponse(BaseModel):
    data_url: str
    seed: int
    error: str | None = None


def _resolve_style_lora(style_key: str, request_override: bool | None) -> tuple[bool, float]:
    """Decide whether the LoRA is on and at what strength for this render.

    Style config is the source of truth; request can override (debug/power
    user). For the "trained-style" preset, strength comes from settings so
    the threshold can be tuned without code changes.
    """
    cfg = _FLUX_STYLES.get(style_key, _FLUX_STYLES["gold-leaf"])
    use_lora = cfg["lora_default"] if request_override is None else request_override
    if not use_lora:
        return (False, 0.0)
    if style_key == "trained-style":
        return (True, get_settings().flux_trained_lora_strength)
    # Other styles that opt into LoRA use whatever they declared.
    return (True, cfg["lora_strength"] or 0.55)


def _build_flux_workflow(req: FluxLocalRequest, seed: int) -> dict:
    """Render the workflow JSON template with this request's parameters.

    Uses str.replace() rather than str.format() because the JSON file's own
    {…} braces (object/array syntax, plus the documentation _comment field)
    confuse format-spec parsing.
    """
    template = _WORKFLOW_PATH.read_text()
    cfg = _FLUX_STYLES.get(req.style, _FLUX_STYLES["gold-leaf"])
    prompt_text = cfg["prompt"].replace("{text}", req.text.replace('"', "'")) + _FLUX_PROMPT_SUFFIX
    use_lora, lora_strength = _resolve_style_lora(req.style, req.use_lora)
    width  = req.width  - (req.width  % 64) or 1024
    height = req.height - (req.height % 64) or 512
    subs = {
        "{prompt}":         json.dumps(prompt_text)[1:-1],   # JSON-escape
        "{seed}":           str(seed),
        "{steps}":          str(max(1, min(8, req.steps))),
        "{lora_name}":      _FLUX_TITLE_LORA if use_lora else "",
        "{lora_strength}":  f"{lora_strength:.2f}",
        "{width}":          str(width),
        "{height}":         str(height),
    }
    populated = template
    for k, v in subs.items():
        populated = populated.replace(k, v)
    graph = json.loads(populated)
    # Remove the human-readable comment; ComfyUI rejects unknown keys at top level.
    graph.pop("_comment", None)

    # When use_lora=False the LoraLoader node validates an empty lora_name and
    # fails. Drop the LoraLoader entirely and rewire CLIPTextEncode / KSampler
    # to the upstream loaders directly.
    if not use_lora:
        graph["5"]["inputs"]["clip"] = ["2", 0]   # CLIPTextEncode pos -> DualCLIPLoader
        graph["6"]["inputs"]["clip"] = ["2", 0]   # CLIPTextEncode neg -> DualCLIPLoader
        graph["8"]["inputs"]["model"] = ["1", 0]  # KSampler -> UnetLoaderGGUF
        graph.pop("4", None)

    if req.bg_remove == "none":
        # SaveImage points at VAEDecode output instead of RMBG.
        graph["11"]["inputs"]["images"] = ["9", 0]
        graph.pop("10", None)
    return graph


async def _comfyui_health(client: httpx.AsyncClient, host: str) -> bool:
    try:
        resp = await client.get(f"{host}/system_stats", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


async def _submit_comfyui_workflow(graph: dict, host: str, timeout_s: int) -> bytes:
    """POST a graph to /prompt, poll /history until done, return output PNG bytes."""
    client_id = uuid.uuid4().hex
    async with httpx.AsyncClient() as client:
        if not await _comfyui_health(client, host):
            raise RuntimeError(
                f"ComfyUI offline at {host} — start it on the Windows box "
                f"(PowerShell: & 'C:\\Program Files\\Python311\\python.exe' E:\\ComfyUI\\main.py --listen 0.0.0.0 --port 8188)"
            )

        submit = await client.post(
            f"{host}/prompt",
            json={"prompt": graph, "client_id": client_id},
            timeout=10.0,
        )
        submit.raise_for_status()
        prompt_id = submit.json().get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return prompt_id: {submit.text}")

        elapsed = 0.0
        while elapsed < timeout_s:
            await asyncio.sleep(1.5)
            elapsed += 1.5
            hist = await client.get(f"{host}/history/{prompt_id}", timeout=10.0)
            if hist.status_code != 200:
                continue
            history = hist.json()
            if prompt_id not in history:
                continue
            outputs = history[prompt_id].get("outputs", {})
            for node_outputs in outputs.values():
                imgs = node_outputs.get("images", [])
                if not imgs:
                    continue
                meta = imgs[0]
                view = await client.get(
                    f"{host}/view",
                    params={
                        "filename": meta["filename"],
                        "subfolder": meta.get("subfolder", ""),
                        "type": meta.get("type", "output"),
                    },
                    timeout=30.0,
                )
                view.raise_for_status()
                return view.content
        raise RuntimeError(f"ComfyUI generation timed out after {timeout_s}s")


@router.post("/flux-local", response_model=FluxLocalResponse)
async def generate_flux_local(body: FluxLocalRequest, user: CurrentUser):
    """
    Generate a transparent title PNG via ComfyUI on the Windows box.

    Pipeline: FLUX.1 Schnell (4 steps) → optional title_card_style_v2 LoRA →
    optional RMBG-2.0 background removal → RGBA PNG.

    ComfyUI must be running at the configured `comfyui_host` (default
    http://100.90.90.68:8188). Returns a clear offline error if not.
    """
    import random
    settings = get_settings()
    seed = body.seed if body.seed > 0 else random.randint(1, 2**31 - 1)

    try:
        graph = _build_flux_workflow(body, seed)
    except (KeyError, json.JSONDecodeError) as exc:
        _log.exception("Failed to build FLUX workflow")
        return FluxLocalResponse(data_url="", seed=seed, error=f"Workflow build failed: {exc}")

    try:
        png_bytes = await _submit_comfyui_workflow(
            graph,
            host=settings.comfyui_host.rstrip("/"),
            timeout_s=settings.comfyui_timeout_seconds,
        )
        b64 = base64.b64encode(png_bytes).decode()
        return FluxLocalResponse(data_url=f"data:image/png;base64,{b64}", seed=seed)
    except RuntimeError as exc:
        # Expected offline / timeout cases — surface message verbatim, no stack trace.
        return FluxLocalResponse(data_url="", seed=seed, error=str(exc))
    except Exception as exc:
        _log.exception("FLUX local generation failed")
        return FluxLocalResponse(data_url="", seed=seed, error=str(exc))


@router.get("/flux-styles")
async def list_flux_styles(user: CurrentUser):
    """List the curated FLUX visual styles for the local AI title mode.

    Styles whose `enabled` is a settings attribute are gated — we look the
    attribute up on the live settings object, so flipping the env var
    (e.g. FLUX_TRAINED_STYLE_ENABLED=1) makes the preset appear in the
    dropdown without a code change.
    """
    settings = get_settings()
    out = []
    for key, cfg in _FLUX_STYLES.items():
        gate = cfg["enabled"]
        if gate != "always" and not getattr(settings, gate, False):
            continue
        out.append({"key": key, "label": cfg["label"]})
    return out
