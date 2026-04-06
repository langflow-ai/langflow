"""Backend i18n utility.

Loads flat JSON locale files from langflow/locales/ and provides a translate()
function used to substitute component display_names in API responses.

Locale files use the same flat dot-notation format as the frontend en.json:
    "components.ChatInput.display_name": "Chat Input"
    "components.ChatInput.inputs.role.display_name": "Role"

Fallback chain: requested locale → "en" → raw default string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_LOCALES_DIR = Path(__file__).parent.parent / "locales"

# { "en": { "components.ChatInput.display_name": "Chat Input", ... }, "fr": {...} }
_translations: dict[str, dict[str, str]] = {}


def _load_translations() -> None:
    """Load all *.json files from the locales directory into memory."""
    if not _LOCALES_DIR.exists():
        return
    for path in _LOCALES_DIR.glob("*.json"):
        locale_code = path.stem  # "en", "fr", "zh-Hans", etc.
        try:
            with path.open(encoding="utf-8") as f:
                _translations[locale_code] = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass


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
    if result:
        return result

    result = _translations.get("en", {}).get(key)
    if result:
        return result

    return default


def get_supported_locales() -> list[str]:
    """Return list of locale codes that have a locale file loaded."""
    if not _translations:
        _load_translations()
    return list(_translations.keys())


def translate_component_dict(all_types: dict[str, Any], locale: str) -> dict[str, Any]:
    """Return a copy of all_types with display_names substituted for locale.

    Never mutates the original dict (which is the shared component cache).
    Only translates:
      - component-level display_name and description
      - template field display_names (inputs)
      - output display_names

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

            # Tier 1 — component-level strings
            translated["display_name"] = translate(
                f"components.{name}.display_name", locale, data.get("display_name", "")
            )
            translated["description"] = translate(f"components.{name}.description", locale, data.get("description", ""))

            # Tier 2 — template field display_names (inputs serialised as dicts)
            if "template" in data and isinstance(data["template"], dict):
                translated["template"] = {**data["template"]}
                for field_name, field in data["template"].items():
                    if isinstance(field, dict) and "display_name" in field:
                        translated["template"][field_name] = {
                            **field,
                            "display_name": translate(
                                f"components.{name}.inputs.{field_name}.display_name",
                                locale,
                                field["display_name"],
                            ),
                        }

            # Tier 2 — output display_names
            if "outputs" in data and isinstance(data["outputs"], list):
                translated["outputs"] = [
                    {
                        **out,
                        "display_name": translate(
                            f"components.{name}.outputs.{out.get('name', '')}.display_name",
                            locale,
                            out.get("display_name", ""),
                        ),
                    }
                    for out in data["outputs"]
                ]

            result[category][name] = translated
    return result
