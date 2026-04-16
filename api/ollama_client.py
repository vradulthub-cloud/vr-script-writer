"""
Ollama HTTP client for routing writing tasks through the local LLM.

The FastAPI backend and Ollama both run on the Windows PC, so we hit
http://localhost:11434 directly — no network, no API cost, no content
policy refusals.

Model selection by task type:
  - short / fast (titles, briefs, SEO): dolphin3:latest (8B uncensored)
  - long-form quality (descriptions, compilation ideas): qwen2.5:14b
  - scripts (purpose-built): vr-scriptwriter:latest

Two entry points:
  - ollama_generate(...) — single-shot completion, returns the full string
  - ollama_stream(...)   — generator yielding text deltas for SSE endpoints
"""

from __future__ import annotations

import json
import logging
from typing import Generator, Optional

import requests

_log = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"

# Task → model map. Endpoints pass the task key.
MODEL_FOR_TASK = {
    "brief":       "dolphin3:latest",
    "title":       "dolphin3:latest",
    "seo":         "dolphin3:latest",
    "description": "qwen2.5:14b",
    "comp_idea":   "qwen2.5:14b",
    "comp_title":  "dolphin3:latest",
    "script":      "vr-scriptwriter:latest",
}


def _model_for(task: str) -> str:
    return MODEL_FOR_TASK.get(task, "dolphin3:latest")


def ollama_generate(
    task: str,
    prompt: str,
    *,
    system: Optional[str] = None,
    max_tokens: int = 400,
    temperature: float = 0.6,
    timeout: int = 90,
) -> str:
    """
    Single-shot generation. Returns the completion text (stripped).
    Raises RuntimeError on any failure — callers should translate to HTTPException.
    """
    model = _model_for(task)
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if system:
        payload["system"] = system

    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        text = (data.get("response") or "").strip()
        if not text:
            raise RuntimeError(f"Ollama ({model}) returned empty response")
        return text
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Ollama not reachable on localhost:11434")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Ollama ({model}) timed out after {timeout}s")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Ollama HTTP {r.status_code}: {e}")


def ollama_stream(
    task: str,
    prompt: str,
    *,
    system: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    timeout: int = 300,
) -> Generator[str, None, None]:
    """
    Streaming generation. Yields text deltas as they arrive.

    Raises RuntimeError on connection failure before any data; per-chunk errors
    are logged and the stream ends (matches Claude SSE behavior).
    """
    model = _model_for(task)
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if system:
        payload["system"] = system

    try:
        with requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=timeout,
            stream=True,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    _log.warning("Ollama sent non-JSON line: %r", line[:100])
                    continue
                delta = chunk.get("response")
                if delta:
                    yield delta
                if chunk.get("done"):
                    break
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Ollama not reachable on localhost:11434")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Ollama ({model}) stream timed out")
