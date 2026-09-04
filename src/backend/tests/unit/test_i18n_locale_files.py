"""Validate shipped backend locale files."""

import json
import re
from pathlib import Path

LOCALES_DIR = Path(__file__).parents[2] / "base" / "langflow" / "locales"
BRACED_TOKEN_PATTERN = re.compile(r"\{\{?[^{}\n]+\}\}?")


def load_locale(locale: str) -> dict[str, str]:
    """Load one backend locale file."""
    with (LOCALES_DIR / f"{locale}.json").open(encoding="utf-8") as locale_file:
        return json.load(locale_file)


def test_russian_locale_matches_english_keys():
    english = load_locale("en")
    russian = load_locale("ru")

    assert russian.keys() == english.keys()
    assert all(isinstance(value, str) and value for value in russian.values())


def test_russian_locale_preserves_braced_tokens():
    english = load_locale("en")
    russian = load_locale("ru")

    mismatches = {
        key: (BRACED_TOKEN_PATTERN.findall(value), BRACED_TOKEN_PATTERN.findall(russian[key]))
        for key, value in english.items()
        if BRACED_TOKEN_PATTERN.findall(value) != BRACED_TOKEN_PATTERN.findall(russian[key])
    }

    assert not mismatches


def test_russian_locale_is_discoverable():
    assert "ru" in {path.stem for path in LOCALES_DIR.glob("*.json")}
