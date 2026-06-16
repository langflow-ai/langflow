"""Shared helpers for recovering a JSON object from a raw LLM reply.

Phase engines that ask the model for a single JSON object (clarification's
question payload, Story 1.1; the diagram generator's xyflow graph, Story 2.1)
all face the same noise: a stray ```` ``` ```` fence or a sentence of prose
wrapped around the braces. These helpers tolerate that and return the parsed
object — or `None` when nothing JSON-shaped can be recovered, so the caller
decides how to degrade.

Pure string functions: no DB, no LLM, no engine imports.
"""

from __future__ import annotations

import json
import re


def strip_code_fences(text: str) -> str:
    """Drop a surrounding ```` ```...``` ```` markdown fence if the model added one."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9]*\s*\n", "", stripped)
        stripped = re.sub(r"\n```\s*$", "", stripped)
    return stripped.strip()


def extract_json_object(text: str) -> dict | None:
    """Best-effort parse of a single JSON object from the model's reply.

    Tolerates a surrounding markdown fence and leading/trailing prose by falling
    back to the first balanced-looking ``{...}`` slice. Returns ``None`` when no
    JSON object can be recovered.
    """
    candidate = strip_code_fences(text)
    try:
        data = json.loads(candidate)
    except (ValueError, TypeError):
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(candidate[start : end + 1])
        except (ValueError, TypeError):
            return None
    return data if isinstance(data, dict) else None
