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

from lfx.base.tools.constants import TOOL_OUTPUT_NAME

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
                translated_node = copy.deepcopy(node)
                description = translated_node["data"]["node"].get("description", "")
                translated_node["data"]["node"]["description"] = translate(i18n_key, locale, description)
                result.append(translated_node)
                continue
        result.append(node)
    return result


def build_component_display_names(all_types_en: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build the set of all known translations for display_name and description per component.

    Also includes all known translations for each input field's display_name.

    Iterates every loaded locale and looks up each component's display_name / description key
    directly in the locale dicts (one key lookup per locale, not a full translate_component_dict
    pass).  The English value is always included as the baseline.

    Returns a dict keyed by normalized component key (e.g. "textinput") where each value is:
        {
            "display_name": [...all locale values...],
            "description": [...all locale values...],
            "fields": {
                "field_name": {"display_name": [...all locale values...]}
            }
        }
    """
    if not _translations:
        _load_translations()

    result: dict[str, dict[str, Any]] = {}

    for components in all_types_en.values():
        for name, data in components.items():
            norm = normalize_component_key(name)
            if norm not in result:
                result[norm] = {"display_name": set(), "description": set(), "fields": {}}

            dn_en = data.get("display_name", "")
            desc_en = data.get("description", "")

            if dn_en:
                key = component_field_key(norm, "display_name", dn_en)
                result[norm]["display_name"].add(dn_en)
                for locale_dict in _translations.values():
                    val = locale_dict.get(key)
                    if val:
                        result[norm]["display_name"].add(val)

            if desc_en:
                key = component_field_key(norm, "description", desc_en)
                result[norm]["description"].add(desc_en)
                for locale_dict in _translations.values():
                    val = locale_dict.get(key)
                    if val:
                        result[norm]["description"].add(val)

            # Collect all known translations for each input field's display_name
            template = data.get("template", {})
            for field_name, field_data in template.items():
                if not isinstance(field_data, dict):
                    continue
                field_dn_en = field_data.get("display_name", "")
                if not field_dn_en:
                    continue
                if field_name not in result[norm]["fields"]:
                    result[norm]["fields"][field_name] = {"display_name": set()}
                field_key = component_field_key(norm, f"inputs.{field_name}.display_name", field_dn_en)
                result[norm]["fields"][field_name]["display_name"].add(field_dn_en)
                for locale_dict in _translations.values():
                    val = locale_dict.get(field_key)
                    if val:
                        result[norm]["fields"][field_name]["display_name"].add(val)

    return {
        k: {
            "display_name": list(v["display_name"]),
            "description": list(v["description"]),
            "fields": {fn: {"display_name": list(fd["display_name"])} for fn, fd in v["fields"].items()},
        }
        for k, v in result.items()
    }


def translate_component_node(comp_name: str, node: dict[str, Any], locale: str) -> dict[str, Any]:
    """Translate display strings in a single component's frontend node dict.

    Covers three tiers:
      - component-level display_name and description
      - template field display_name, info, placeholder
      - output display_name and info

    Translation is idempotent: if a field already holds a translated value its
    hash won't match the English key, so translate() falls back to the value
    unchanged.  Never mutates the input dict.
    """
    translated: dict[str, Any] = {**node}
    norm = normalize_component_key(comp_name)

    # Tier 1 — component-level strings
    for field in ("display_name", "description"):
        val = node.get(field, "")
        if val:
            translated[field] = translate(component_field_key(norm, field, val), locale, val)

    # Tier 2 — template field display_name, info, placeholder
    if "template" in node and isinstance(node["template"], dict):
        translated["template"] = {**node["template"]}
        for field_name, field in node["template"].items():
            if isinstance(field, dict):
                field_updates = {}
                for sub in ("display_name", "info", "placeholder"):
                    val = field.get(sub, "")
                    if val:
                        field_updates[sub] = translate(
                            component_field_key(norm, f"inputs.{field_name}.{sub}", val), locale, val
                        )
                if field_updates:
                    translated["template"][field_name] = {**field, **field_updates}

    # Tier 3 — output display_name and info
    if "outputs" in node and isinstance(node["outputs"], list):
        translated["outputs"] = []
        for out in node["outputs"]:
            if not isinstance(out, dict):
                translated["outputs"].append(out)
                continue
            out_name = out.get("name", "")
            # The tool-mode output is injected dynamically (not a static class output), so
            # it's stored under the sentinel norm "_toolmode" shared across all components.
            out_norm = "_toolmode" if out_name == TOOL_OUTPUT_NAME else norm
            out_updates = {}
            for sub in ("display_name", "info"):
                val = out.get(sub, "")
                if val:
                    out_updates[sub] = translate(
                        component_field_key(out_norm, f"outputs.{out_name}.{sub}", val), locale, val
                    )
            translated["outputs"].append({**out, **out_updates} if out_updates else out)

    return translated


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
            result[category][name] = translate_component_node(name, data, locale)
    return result
