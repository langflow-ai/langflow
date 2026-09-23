"""Check the Korean locale files against the English sources and the style guide.

Covers both locale files:
  - frontend: src/frontend/src/locales/ko.json   (must mirror every key in en.json)
  - backend:  src/backend/base/langflow/locales/ko.json
              (descriptions and help text only; names stay English by design)

Errors (exit code 1): missing or unknown keys, mismatched {{variables}}, {placeholders}
or <n> tags, empty values, backend name keys that should have been left out.
Warnings: glossary violations, translationese, banned characters, inconsistent
translations of the same English string, labels much longer than the English.

The rules come from src/frontend/src/locales/KO_STYLE_GUIDE.md.

Usage (from the repository root):
    uv run python scripts/i18n/check_ko.py
    uv run python scripts/i18n/check_ko.py --only frontend
    uv run python scripts/i18n/check_ko.py --file part.json --against frontend
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "src/frontend/src/locales"
BACKEND_DIR = REPO_ROOT / "src/backend/base/langflow/locales"

I18N_VAR = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
PY_VAR = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")
TAG = re.compile(r"</?\d+>")
# ASCII only, so a Korean particle glued to a URL is not swallowed. Parentheses are left out because
# markdown links wrap the URL in them. Trailing punctuation is stripped below.
URL = re.compile(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'*+,;=%]+")
HANGUL = re.compile(r"[가-힣]")

# A value this short in English should not balloon in Korean: it is a label.
SHORT_LABEL_CHARS = 24
# Below this many English words, an identical Korean value may just be a proper noun.
UNTRANSLATED_MIN_WORDS = 4

# Spelled as code points: these characters are the ones being searched for, so
# writing them literally here would trip the repo's ambiguous-character lint.
BANNED_CHARS = {
    chr(0x2014): "em dash",
    chr(0x2013): "en dash",
    chr(0x00B7): "middle dot",
    chr(0x00A7): "section sign",
}
# Straight and curly closing quotes that can sit between a variable and a particle.
CLOSING_QUOTES = "\"'" + chr(0x201D) + chr(0x2019)

# Terms the style guide keeps in English. A Korean rendering is a glossary violation.
GLOSSARY = [
    (r"플로우", "Flow"),
    (r"컴포넌트", "Component"),
    (r"에이전트", "Agent"),
    (r"플레이그라운드", "Playground"),
    (r"템플릿", "Template"),
    (r"프롬프트", "Prompt"),
    (r"제공자|프로바이더|공급자", "Provider"),
    (r"(?<![가-힣])모델", "Model"),
    (r"(?<![가-힣])툴(?![가-힣])|(?<![가-힣])도구", "Tool"),
    (r"임베딩", "Embedding"),
    (r"토큰", "Token"),
    (r"웹훅|웹후크", "Webhook"),
    (r"청크", "Chunk"),
    (r"지식 ?베이스|지식 ?기반", "Knowledge Base"),
    (r"벡터 ?(?:스토어|저장소)", "Vector Store"),
    (r"(?:전역|글로벌) ?변수", "Global Variable"),
    (r"어시스턴트", "Assistant"),
    (r"(?<![가-힣])번들", "Bundles"),
    (r"MCP ?서버", "MCP Server"),
    (r"API ?키", "API Key"),
    (r"언어 ?모델", "Language Model (field name)"),
]

# The most common translationese in UI strings. The full list lives in the style guide.
TRANSLATIONESE = [
    (r"성공적으로", "successfully: drop it"),
    (r"당신|귀하|사용자님", "do not address the user"),
    (r"십시오|시기 바랍니다", "use ~하세요"),
    (r"(?:시|하)겠습니까", "use ~할까요?"),
    (r"정말로? ", "drop 정말(로)"),
    (r"에 실패(?:했|하였)|(?:을|를) 실패(?:했|하였)", "use ~하지 못했습니다"),
    (r"는 (?:동안|중에?|도중에?) (?:오류|에러|문제)", "use ~하지 못했습니다"),
    (r"발견되지 않", "use ~가 없습니다"),
    (r"(?:\d|\}\})\s*개의 ", "write '세션 3개', not '3개의 세션'"),
    (r"로딩|(?<![업운])(?<!페이)로드(?:하|되|에|를|할|가| 중|중)", "use 불러오다"),
    (r"유효하지 않", "use 올바르지 않은 / 형식이 맞지 않습니다"),
    (r"사용 가능한 ", "usually just drop it"),
    (r"요구(?:됩니다|된다|되는)", "use 입력하세요 / 필수입니다"),
    (r"기 위(?:해|하여|한)", "use ~하려면 / ~하도록"),
    (r"(?:을|를) 위한 ", "write 'A B', not 'A를 위한 B'"),
    (r"에 대(?:해|한)", "use ~를 or rephrase"),
    (r"(?:을|를) 통(?:해|한)", "use ~로"),
    (r"(?:로|으로)부터", "use ~에서"),
    (r"에 의(?:해|한)", "use the active voice"),
    (r"함으로써", "use ~해서 / ~하면"),
    (r"(?<![가-힣])(?:하나의|한 개의) ", "drop the article"),
    (r"각각의 ", "use ~마다 / ~별"),
    (r"(?:^|\s)(?:만약|만일) ", "drop it, ~면 is enough"),
    (r"[가-힣] 필요가 있", "use ~해야 합니다"),
    (r"(?:을|를) 허용|도록 허용", "use ~할 수 있습니다"),
    (r"(?:을|를) 가능하게", "use ~할 수 있습니다"),
    (r"(?:을|를) 필요로", "use ~가 필요합니다"),
    (
        r"(?:파일|항목|설정|데이터|결과|옵션|메시지|값|키|노드|문서|기능|요청|오류|세션|버전|폴더|변수|필드|링크)들",
        "no plural 들 on things",
    ),
    (r"다양한|혁신적|강력한|원활한|손쉽게|효율적으로", "empty modifier"),
    (
        r"을\(를\)|를\(을\)|이\(가\)|가\(이\)|은\(는\)|는\(은\)|와\(과\)|과\(와\)|\(으\)로",
        "no paired particles, reorder the sentence",
    ),
    (
        r"\}\}[" + CLOSING_QUOTES + r")\]]?(?:을|를|이|가|은|는|와|과|로|으로)(?=[\s.,?!]|$)",
        "no batchim-dependent particle right after a variable",
    ),
    (r"\be\.g\.|\bi\.e\.|\betc\.", "use 예: / 즉 / 등"),
]

# Backend keys that must stay out of ko.json so the English name shows through.
BACKEND_NAME_KEY = re.compile(r"^components\..*\.display_name\.[0-9a-f]{8}$|^starter_flows\..*\.name$")


def load(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def width(text: str) -> int:
    """Approximate rendered width: wide (Hangul, CJK) characters count double."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def backend_expected_keys(en: dict[str, str]) -> list[str]:
    """Backend keys the style guide says to translate."""
    keys = []
    for key in en:
        if BACKEND_NAME_KEY.match(key):
            continue
        if key.startswith("components."):
            if key.split(".")[-2] in ("description", "info", "placeholder"):
                keys.append(key)
        elif key.startswith(("starter_flows.", "template_notes.")):
            keys.append(key)
    return keys


class Report:
    def __init__(self, title: str) -> None:
        self.title = title
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, key: str, message: str) -> None:
        self.errors.append(f"  [{key}] {message}")

    def warn(self, key: str, message: str) -> None:
        self.warnings.append(f"  [{key}] {message}")

    def print(self, max_lines: int) -> None:
        print(f"\n=== {self.title} ===")
        for label, lines in (("ERROR", self.errors), ("WARN", self.warnings)):
            if not lines:
                continue
            print(f" {label} {len(lines)}")
            for line in lines[:max_lines]:
                print(line)
            if len(lines) > max_lines:
                print(f"  ... {len(lines) - max_lines} more (use --max 0 to show all)")
        if not self.errors and not self.warnings:
            print(" OK")


def tag_order_error(value: str) -> str | None:
    """Why the numbered tags in ``value`` are malformed, or None when they pair up.

    Counting tags is not enough: ``</1>Chat Input<1>`` has the same counts as
    ``<1>Chat Input</1>``. A translation may move a complete pair, not split it.
    """
    open_tags: list[str] = []
    for tag in TAG.findall(value):
        number = tag.strip("</>")
        if tag.startswith("</"):
            if not open_tags:
                return f"{tag} closes a tag that was never opened"
            if open_tags[-1] != number:
                return f"{tag} closes <{open_tags[-1]}>"
            open_tags.pop()
        else:
            open_tags.append(number)
    if open_tags:
        return f"<{open_tags[-1]}> is never closed"
    return None


def check_value(report: Report, key: str, en_value: str, ko_value: str, *, markdown: bool) -> None:
    if not isinstance(ko_value, str):
        report.error(key, "value is not a string")
        return
    if not ko_value.strip():
        report.error(key, "empty value (would fall back to English)")
        return

    for pattern, name in ((I18N_VAR, "{{variable}}"), (PY_VAR, "{placeholder}"), (TAG, "<n> tag"), (URL, "URL")):
        expected, actual = Counter(pattern.findall(en_value)), Counter(pattern.findall(ko_value))
        if pattern is URL:
            expected = Counter(u.rstrip(".,;:!?)'\"") for u in expected.elements())
            actual = Counter(u.rstrip(".,;:!?)'\"") for u in actual.elements())
        if expected != actual:
            missing = sorted((expected - actual).elements())
            added = sorted((actual - expected).elements())
            report.error(key, f"{name} mismatch: missing {missing}, unexpected {added}")

    malformed = tag_order_error(ko_value)
    if malformed:
        report.error(key, f"<n> tags out of order: {malformed}")

    if markdown:
        for marker, name in (
            (r"(?m)^#{1,6} ", "heading"),
            (r"(?m)^\s*(?:[-*]|\d+\.) ", "list item"),
            (r"```", "code fence"),
            (r"\]\(", "link"),
        ):
            if len(re.findall(marker, en_value)) != len(re.findall(marker, ko_value)):
                report.error(key, f"markdown {name} count differs from the English note")
        if ko_value.count("**") % 2:
            report.error(key, "unbalanced ** bold markers")

    for char, name in BANNED_CHARS.items():
        if char in ko_value:
            report.warn(key, f"banned character {name} ({char})")
    for pattern, term in GLOSSARY:
        found = re.search(pattern, ko_value)
        if found:
            report.warn(key, f"glossary: '{found.group(0)}' should stay English as {term} | {ko_value[:50]}")
    for pattern, why in TRANSLATIONESE:
        found = re.search(pattern, ko_value)
        if found:
            report.warn(key, f"translationese '{found.group(0).strip()}': {why} | {ko_value[:50]}")

    if not HANGUL.search(ko_value) and len(en_value.split()) >= UNTRANSLATED_MIN_WORDS and ko_value == en_value:
        report.warn(key, f"looks untranslated | {ko_value[:60]}")
    if not markdown and len(en_value) <= SHORT_LABEL_CHARS and width(ko_value) > 2 * len(en_value) + 6:
        report.warn(key, f"label is much longer than the English ({len(en_value)} → {width(ko_value)}) | {ko_value}")


def check_frontend(ko_path: Path, *, partial: bool, max_lines: int) -> int:
    en = load(FRONTEND_DIR / "en.json")
    ko = load(ko_path)
    report = Report(f"frontend: {ko_path}  ({len(ko)}/{len(en)} keys)")

    if not partial:
        for key in en:
            if key not in ko:
                report.error(key, "missing")
        if [k for k in ko if k in en] != [k for k in en if k in ko]:
            report.warn("-", "key order differs from en.json")
    for key, value in ko.items():
        if key not in en:
            report.error(key, "not in en.json")
            continue
        check_value(report, key, en[key], value, markdown=False)

    for key in ko:
        for suffix, twin in (("_one", "_other"), ("_other", "_one")):
            if key.endswith(suffix):
                twin_key = key[: -len(suffix)] + twin
                if twin_key in en and twin_key not in ko and partial is False:
                    report.error(key, f"plural twin {twin_key} is missing")

    report.print(max_lines)
    return len(report.errors)


def check_backend(ko_path: Path, *, partial: bool, max_lines: int) -> int:
    en = load(BACKEND_DIR / "en.json")
    ko = load(ko_path)
    expected = backend_expected_keys(en)
    report = Report(f"backend: {ko_path}  ({len(ko)}/{len(expected)} keys)")

    if not partial:
        missing = [key for key in expected if key not in ko]
        if missing:
            report.warn("-", f"{len(missing)} translatable keys still missing, e.g. {missing[0]}")
    by_english: dict[str, set[str]] = defaultdict(set)
    for key, value in ko.items():
        if key not in en:
            report.error(key, "not in en.json (keys carry a hash of the English text, never edit them)")
            continue
        if BACKEND_NAME_KEY.match(key):
            report.error(key, "name keys must be left out so the English name shows")
            continue
        check_value(report, key, en[key], value, markdown=key.startswith("template_notes."))
        # check_value has already reported a non-string value; a set cannot hold it.
        if isinstance(value, str):
            by_english[en[key]].add(value)

    for english, translations in by_english.items():
        if len(translations) > 1:
            report.warn("-", f"same English, {len(translations)} translations: {english[:60]}")

    report.print(max_lines)
    return len(report.errors)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=("frontend", "backend"), help="check one locale file only")
    parser.add_argument("--file", type=Path, help="check a partial translation file instead of ko.json")
    parser.add_argument("--against", choices=("frontend", "backend"), help="which en.json a --file belongs to")
    parser.add_argument("--max", type=int, default=40, help="lines to print per section, 0 for all")
    args = parser.parse_args()
    max_lines = args.max or 10**9

    if args.file:
        if not args.against:
            parser.error("--file needs --against frontend|backend")
        checker = check_frontend if args.against == "frontend" else check_backend
        sys.exit(1 if checker(args.file, partial=True, max_lines=max_lines) else 0)

    errors = 0
    for name, directory, checker in (
        ("frontend", FRONTEND_DIR, check_frontend),
        ("backend", BACKEND_DIR, check_backend),
    ):
        if args.only and args.only != name:
            continue
        path = directory / "ko.json"
        if not path.exists():
            # Counted as an error: a full run must not pass with a locale file gone.
            print(f"\n=== {name}: {path} is missing ===")
            errors += 1
            continue
        errors += checker(path, partial=False, max_lines=max_lines)

    print(f"\n{'FAILED' if errors else 'PASSED'}: {errors} error(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
