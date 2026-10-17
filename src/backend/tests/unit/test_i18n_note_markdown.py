"""Guards the translated template notes against markdown that no longer renders.

Template notes render through react-markdown, which follows CommonMark. A
translation can keep every word and still break the markup around them:
``2.`` turns into ``2、`` and the step folds into the one above it, or
``**URL **`` and ``**「URL」**の`` stop being bold and leave the asterisks on
the canvas. Keys and placeholders stay intact, so nothing else catches it.

Every translated note is parsed as CommonMark and must come out with the same
structure as its English source. Inline code is not compared, because a
translation may quote an example sentence instead of setting it as code; a
backtick left behind as plain text is still reported.
"""

import json
from collections import Counter
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

LOCALES_DIR = Path(__file__).parents[2] / "base" / "langflow" / "locales"
NOTE_PREFIX = "template_notes."

_COMMONMARK = MarkdownIt("commonmark")
_STRUCTURE_TOKENS = {
    "bullet_list_open",
    "ordered_list_open",
    "list_item_open",
    "strong_open",
    "em_open",
    "link_open",
    "fence",
    "code_block",
    "hr",
}


def _load(locale: str) -> dict[str, str]:
    return json.loads((LOCALES_DIR / f"{locale}.json").read_text(encoding="utf-8"))


def _structure(markdown: str) -> Counter[str]:
    """Count what a reader sees: headings, list items, emphasis, links, and markup left over as text."""
    counts: Counter[str] = Counter()
    for token in _COMMONMARK.parse(markdown):
        if token.type == "heading_open":
            counts[token.tag] += 1
        elif token.type in _STRUCTURE_TOKENS:
            counts[token.type] += 1
        for child in token.children or []:
            if child.type in _STRUCTURE_TOKENS:
                counts[child.type] += 1
            elif child.type == "text":
                counts["literal **"] += child.content.count("**")
                counts["literal `"] += child.content.count("`")
    return +counts


ENGLISH_NOTES = {key: value for key, value in _load("en").items() if key.startswith(NOTE_PREFIX)}
TRANSLATED_LOCALES = sorted(path.stem for path in LOCALES_DIR.glob("*.json") if path.stem != "en")


def test_english_template_notes_are_found():
    assert ENGLISH_NOTES, f"no {NOTE_PREFIX}* keys in {LOCALES_DIR / 'en.json'}"
    assert TRANSLATED_LOCALES


@pytest.mark.parametrize("locale", TRANSLATED_LOCALES)
def test_translated_template_notes_render_like_english(locale: str):
    translated = _load(locale)
    broken = {}
    for key, english in ENGLISH_NOTES.items():
        if key not in translated:
            continue
        expected, actual = _structure(english), _structure(translated[key])
        if expected != actual:
            broken[key] = {
                name: (expected[name], actual[name])
                for name in sorted(expected | actual)
                if expected[name] != actual[name]
            }

    assert broken == {}, f"{locale}: notes whose markdown renders differently from English (english, {locale})"


@pytest.mark.parametrize(
    ("english", "translated"),
    [
        pytest.param("1. One\n2. Two", "1. One\n2、 Two", id="list-marker-lost"),
        pytest.param("Open the **URL** tool.", "Open the **URL **tool.", id="space-inside-bold"),
        pytest.param("Under **Knowledge Bases**.", "**「ナレッジベース」**の下に", id="cjk-punctuation-bold"),
        pytest.param("Type `hello` here.", "Type `hello here.", id="unmatched-backtick"),
    ],
)
def test_structure_flags_markup_that_no_longer_renders(english: str, translated: str):
    assert _structure(english) != _structure(translated)


def test_structure_allows_a_quoted_example_instead_of_code():
    assert _structure("Type `Write the post` in the field.") == _structure("フィールドに「投稿を書く」と入力します。")
