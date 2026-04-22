"""Backend i18n utility.

Loads flat JSON locale files from langflow/locales/ and provides a translate()
function used to substitute component display_names in API responses.

## Component key scheme

Component strings use a hybrid key: human-readable path + content hash suffix.

    "components.{norm_name}.{field_path}.{sha256[:8]}"

Examples:
    "components.prompttemplate.display_name.a1b2c3d4": "Prompt Template"
    "components.prompttemplate.inputs.template.display_name.f9e8d7c6": "Template"
    "components.chatinput.outputs.message.display_name.12345678": "Chat Message"

The norm_name is the component registry key with spaces removed and lowercased
("Prompt Template" → "prompttemplate"), making it stable across space/case renames.

The 8-char SHA-256 suffix is derived from the English value. When a string
changes (e.g. "Prompt Template" → "New Prompt Template"), the hash suffix
changes, the old key becomes orphaned, and the new key is picked up by GP on
the next upload/translate/download cycle — guaranteeing fresh translations.

Other namespaces keep human-readable keys:
    "starter_flows.{slug}.name"
    "notes.{hash}"

Fallback chain: requested locale → "en" → raw default string.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any

from langflow.utils.i18n_keys import (
    component_field_key,
    normalize_component_key,
)
from langflow.utils.i18n_keys import (
    safe_flow_key as _safe_flow_key,
)

logger = logging.getLogger(__name__)

_LOCALES_DIR = Path(__file__).parent.parent / "locales"

_translations: dict[str, dict[str, str]] = {}
_translations_lock = threading.Lock()


def _load_translations() -> None:
    """Load all *.json files from the locales directory into memory.

    Uses double-checked locking: the fast path (already loaded) skips the lock,
    the slow path (first load) acquires it and re-checks to avoid duplicate work
    from concurrent callers at cold start.
    """
    with _translations_lock:
        if _translations:
            return
        if not _LOCALES_DIR.exists():
            return
        for path in _LOCALES_DIR.glob("*.json"):
            locale_code = path.stem  # "en", "fr", "zh-Hans", etc.
            try:
                with path.open(encoding="utf-8") as f:
                    _translations[locale_code] = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load locale %s: %s", locale_code, exc)


def translate(key: str, locale: str, default: str) -> str:
    """Return the translated string for key in locale, with fallback.

    Fallback chain:
      1. Requested locale dict
      2. English ("en") dict
      3. Raw default string (original English value from API cache)
    """
    if not _translations:
        _load_translations()

    result = _translations.get(locale, {}).get(key)
    if result is not None:
        return result

    result = _translations.get("en", {}).get(key)
    if result is not None:
        return result

    return default


def get_supported_locales() -> list[str]:
    """Return list of locale codes that have a locale file loaded."""
    if not _translations:
        _load_translations()
    return list(_translations.keys())


def translate_starter_flows(flow_reads: list, locale: str) -> list:
    """Return copies of flow_reads with name/description translated for locale."""
    result = []
    for flow in flow_reads:
        key = _safe_flow_key(flow.name or "")
        flow_copy = copy.copy(flow)
        flow_copy.name_key = key
        flow_copy.name = translate(f"starter_flows.{key}.name", locale, flow.name or "")
        flow_copy.description = (
            translate(f"starter_flows.{key}.description", locale, flow.description or "") or flow_copy.description
        )
        result.append(flow_copy)
    return result


def translate_flow_notes(nodes: list[dict], locale: str) -> list[dict]:
    """Return a copy of nodes with note node descriptions translated for locale.

    Reads i18n_key from node.data.node (baked in by bake_note_keys.py) and
    substitutes the translated markdown. Nodes without i18n_key are passed through
    unchanged. Never mutates the input list.
    """
    result = []
    for node in nodes:
        if node.get("type") == "noteNode":
            i18n_key = node.get("data", {}).get("node", {}).get("i18n_key")
            if i18n_key:
                node = copy.deepcopy(node)
                description = node["data"]["node"].get("description", "")
                node["data"]["node"]["description"] = translate(i18n_key, locale, description)
        result.append(node)
    return result


def translate_component_dict(all_types: dict[str, Any], locale: str) -> dict[str, Any]:
    """Return a copy of all_types with display_names substituted for locale.

    Never mutates the original dict (which is the shared component cache).
    Translates:
      - component-level display_name and description
      - template field display_names, info, and placeholders (inputs)
      - output display_names and info

    Keys are hybrid: human-readable path + content hash suffix.
    See module docstring for key format details.

    Args:
        all_types: The cached component dict from get_and_cache_all_types_dict()
        locale: Normalised locale code e.g. "fr", "zh-Hans"

    Returns:
        New dict with translated strings; untranslated keys fall back to English.
    """
    result: dict[str, Any] = {}
    for category, components in all_types.items():
        result[category] = {}
        for name, data in components.items():
            translated: dict[str, Any] = {**data}
            norm = normalize_component_key(name)

            # Tier 1 — component-level strings
            display_name_en = data.get("display_name", "")
            description_en = data.get("description", "")
            if display_name_en:
                translated["display_name"] = translate(
                    component_field_key(norm, "display_name", display_name_en),
                    locale,
                    display_name_en,
                )
            if description_en:
                translated["description"] = translate(
                    component_field_key(norm, "description", description_en),
                    locale,
                    description_en,
                )

            # Tier 2 — template field display_names, info, and placeholders
            if "template" in data and isinstance(data["template"], dict):
                translated["template"] = {**data["template"]}
                for field_name, field in data["template"].items():
                    if isinstance(field, dict):
                        field_updates = {}
                        field_display_en = field.get("display_name", "")
                        field_info_en = field.get("info", "")
                        field_placeholder_en = field.get("placeholder", "")
                        if field_display_en:
                            field_updates["display_name"] = translate(
                                component_field_key(norm, f"inputs.{field_name}.display_name", field_display_en),
                                locale,
                                field_display_en,
                            )
                        if field_info_en:
                            field_updates["info"] = translate(
                                component_field_key(norm, f"inputs.{field_name}.info", field_info_en),
                                locale,
                                field_info_en,
                            )
                        if field_placeholder_en:
                            field_updates["placeholder"] = translate(
                                component_field_key(norm, f"inputs.{field_name}.placeholder", field_placeholder_en),
                                locale,
                                field_placeholder_en,
                            )
                        if field_updates:
                            translated["template"][field_name] = {**field, **field_updates}

            # Tier 2 — output display_names and info
            if "outputs" in data and isinstance(data["outputs"], list):
                translated["outputs"] = []
                for out in data["outputs"]:
                    out_name = out.get("name", "")
                    out_display_en = out.get("display_name", "")
                    out_info_en = out.get("info", "")
                    out_updates = {}
                    if out_display_en:
                        out_updates["display_name"] = translate(
                            component_field_key(norm, f"outputs.{out_name}.display_name", out_display_en),
                            locale,
                            out_display_en,
                        )
                    if out_info_en:
                        out_updates["info"] = translate(
                            component_field_key(norm, f"outputs.{out_name}.info", out_info_en),
                            locale,
                            out_info_en,
                        )
                    translated["outputs"].append({**out, **out_updates} if out_updates else out)

            result[category][name] = translated
    return result
