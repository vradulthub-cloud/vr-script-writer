"""
training_data.py
Stores accepted scripts as few-shot training examples.
Each accepted script is saved to training_data.json and used to guide
future generations for the same studio via few-shot prompting.
"""

import json
import os
from datetime import datetime

TRAINING_FILE = os.path.join(os.path.dirname(__file__), "training_data.json")


def load_training_data() -> list:
    if not os.path.exists(TRAINING_FILE):
        return []
    try:
        with open(TRAINING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_accepted(studio: str, parsed: dict, fields: dict, research_context: str = "") -> None:
    """Save an accepted script to the training dataset."""
    data = load_training_data()
    data.append({
        "timestamp": datetime.now().isoformat(),
        "studio": studio,
        "female": parsed.get("female", ""),
        "male": parsed.get("male", ""),
        "destination": parsed.get("destination", ""),
        "scene_type": parsed.get("scene_type", ""),
        "research": research_context,
        "theme": fields.get("theme", ""),
        "plot": fields.get("plot", ""),
        "set_design": fields.get("set_design", ""),
        "props": fields.get("props", ""),
        "wardrobe_female": fields.get("wardrobe_female", ""),
        "wardrobe_male": fields.get("wardrobe_male", ""),
    })
    with open(TRAINING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_rejected(studio: str, parsed: dict, fields: dict, feedback: str = "") -> None:
    """Save a rejected script with feedback (for analysis, not used as examples)."""
    rejected_file = os.path.join(os.path.dirname(__file__), "rejected_data.json")
    try:
        existing = json.load(open(rejected_file, encoding="utf-8")) if os.path.exists(rejected_file) else []
    except Exception:
        existing = []
    existing.append({
        "timestamp": datetime.now().isoformat(),
        "studio": studio,
        "female": parsed.get("female", ""),
        "theme": fields.get("theme", ""),
        "plot": fields.get("plot", ""),
        "feedback": feedback,
    })
    with open(rejected_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def get_examples_for_studio(studio: str, n: int = 2) -> list:
    """Return up to n most recent accepted scripts for a given studio."""
    data = load_training_data()
    matched = [e for e in data if e.get("studio", "").lower() == studio.lower()]
    return matched[-n:] if matched else []


def format_example_for_prompt(entry: dict) -> str:
    """Format a training entry as a few-shot example block."""
    lines = [
        f"THEME: {entry['theme']}",
        f"",
        f"PLOT:",
        entry["plot"],
        f"",
        f"SET DESIGN: {entry['set_design']}",
        f"",
        f"PROPS: {entry['props']}",
        f"",
        f"WARDROBE - FEMALE: {entry['wardrobe_female']}",
    ]
    if entry.get("wardrobe_male"):
        lines += ["", f"WARDROBE - MALE: {entry['wardrobe_male']}"]
    return "\n".join(lines)


def training_stats() -> dict:
    """Return basic stats about the training dataset."""
    data = load_training_data()
    by_studio = {}
    for entry in data:
        s = entry.get("studio", "Unknown")
        by_studio[s] = by_studio.get(s, 0) + 1
    return {"total": len(data), "by_studio": by_studio}
