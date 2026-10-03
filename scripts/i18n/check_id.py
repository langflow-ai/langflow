"""Check the Indonesian locale files against the English sources and the style guide.

Covers both locale files:
  - frontend: src/frontend/src/locales/id.json
              (must mirror every key in en.json)
  - backend:  src/backend/base/langflow/locales/id.json
              (descriptions/help text/template notes only; names stay English)

Hard errors (exit code 1) cover structural problems: missing locale files,
invalid JSON, missing or unexpected keys, non-string/empty values, placeholder
mismatches, malformed numbered tags, and safely detectable URL/Markdown/code
invariant changes.

Warnings are conservative language-quality hints: likely untranslated English
prose, inconsistent translations of identical English source strings, selected
protected-term substitutions, suspicious mixed-language forms, and unusually
large short-label expansion.

Rules and terminology are documented in:
  src/frontend/src/locales/ID_STYLE_GUIDE.md

Usage (from the repository root):
    uv run python scripts/i18n/check_id.py
    uv run python scripts/i18n/check_id.py --only frontend
    uv run python scripts/i18n/check_id.py --only backend
    uv run python scripts/i18n/check_id.py --file part.json --against frontend
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "src/frontend/src/locales"
BACKEND_DIR = REPO_ROOT / "src/backend/base/langflow/locales"

I18N_VAR = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
# Exclude {{name}} and ${name}; those are validated separately.
PY_VAR = re.compile(r"(?<![\{$])\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")
DOLLAR_VAR = re.compile(r"\$\{([^{}]+)\}")
PRINTF_VAR = re.compile(
    r"%(?:\([A-Za-z_][A-Za-z0-9_]*\))?"
    r"[-+#0 ']*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?"
    r"[diouxXeEfFgGcrsa]"
)
TAG = re.compile(r"</?\d+>")
# ASCII only, matching the Korean checker precedent. Parentheses are omitted
# because Markdown links wrap URLs in them. Trailing punctuation is stripped.
URL = re.compile(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'*+,;=%]+")
MARKDOWN_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")
INLINE_CODE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
FENCED_CODE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
ENV_VAR = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")

SHORT_LABEL_CHARS = 28
UNTRANSLATED_MIN_WORDS = 6
BACKEND_KEY_MIN_PARTS = 2
ENGLISH_PROSE_MIN_WORDS = 10
ENGLISH_PROSE_MIN_FUNCTION_WORDS = 4
ENGLISH_PROSE_DOMINANCE_MARGIN = 3
INCONSISTENT_TRANSLATION_PREVIEW_LIMIT = 3

# Backend keys intentionally omitted so the English display/name remains visible.
BACKEND_NAME_KEY = re.compile(r"^components\..*\.display_name\.[0-9a-f]{8}$|^starter_flows\..*\.name$")

# Warning-only terminology checks. They run only when the English source uses
# the protected Langflow term and the Indonesian value replaces it with the
# listed rendering while omitting the original term.
PROTECTED_TERM_WARNINGS: tuple[tuple[str, re.Pattern[str], re.Pattern[str]], ...] = (
    ("Flow", re.compile(r"(?<![A-Za-z])Flow(?![A-Za-z])"), re.compile(r"\balur\b", re.IGNORECASE)),
    (
        "Component",
        re.compile(r"(?<![A-Za-z])Component(?![A-Za-z])"),
        re.compile(r"\bkomponen\b", re.IGNORECASE),
    ),
    ("Agent", re.compile(r"(?<![A-Za-z])Agent(?![A-Za-z])"), re.compile(r"\bagen\b", re.IGNORECASE)),
    ("Tool", re.compile(r"(?<![A-Za-z])Tool(?![A-Za-z])"), re.compile(r"\balat\b", re.IGNORECASE)),
    (
        "Provider",
        re.compile(r"(?<![A-Za-z])Provider(?![A-Za-z])"),
        re.compile(r"\bpenyedia\b", re.IGNORECASE),
    ),
    (
        "Prompt",
        re.compile(r"(?<![A-Za-z])Prompt(?![A-Za-z])"),
        re.compile(r"\bperintah\b", re.IGNORECASE),
    ),
    (
        "Template",
        re.compile(r"(?<![A-Za-z])Template(?![A-Za-z])"),
        re.compile(r"\btemplat\b", re.IGNORECASE),
    ),
    (
        "Playground",
        re.compile(r"(?<![A-Za-z])Playground(?![A-Za-z])"),
        re.compile(r"\b(?:area|ruang)\s+uji\b", re.IGNORECASE),
    ),
    (
        "Embedding",
        re.compile(r"(?<![A-Za-z])Embedding(?![A-Za-z])"),
        re.compile(r"\bpenyematan\b", re.IGNORECASE),
    ),
    (
        "Vector Store",
        re.compile(r"(?<![A-Za-z])Vector Store(?![A-Za-z])"),
        re.compile(r"\bpenyimpanan\s+vektor\b", re.IGNORECASE),
    ),
    (
        "Knowledge Base",
        re.compile(r"(?<![A-Za-z])Knowledge Base(?![A-Za-z])"),
        re.compile(r"\bbasis\s+pengetahuan\b", re.IGNORECASE),
    ),
    (
        "API Key",
        re.compile(r"(?<![A-Za-z])API Key(?![A-Za-z])"),
        re.compile(r"\bkunci\s+API\b", re.IGNORECASE),
    ),
    (
        "MCP Server",
        re.compile(r"(?<![A-Za-z])MCP Server(?![A-Za-z])"),
        re.compile(r"\bserver\s+MCP\b", re.IGNORECASE),
    ),
    (
        "Global Variable",
        re.compile(r"(?<![A-Za-z])Global Variable(?![A-Za-z])"),
        re.compile(r"\bvariabel\s+global\b", re.IGNORECASE),
    ),
)

# Narrow warning patterns based on wording the Indonesian locale deliberately
# avoids. These are hints only; they never cause a nonzero exit code.
SUSPICIOUS_INDONESIAN = (
    (re.compile(r"\bBuild Flow kembali\b", re.IGNORECASE), "prefer 'Build ulang Flow'"),
    (re.compile(r"\bRun workflow gagal\b", re.IGNORECASE), "prefer 'Workflow gagal dijalankan'"),
    (re.compile(r"\bURL Authorization\b", re.IGNORECASE), "prefer 'URL Otorisasi'"),
    (
        re.compile(r"\b(?:di|meng|ter)-(?:resolve|strip|stream|cache|index|deploy|build|run)\w*\b", re.IGNORECASE),
        "avoid hybrid Indonesian-prefix + English-verb forms when natural Indonesian is available",
    ),
    (
        re.compile(r"\bworkaround untuk continuity\b", re.IGNORECASE),
        "prefer natural Indonesian around the retained technical term",
    ),
    (re.compile(r"\bsecara mulus\b", re.IGNORECASE), "prefer a natural phrase such as 'dengan lancar'"),
    (re.compile(r"\bquestion-answering\b", re.IGNORECASE), "prefer 'tanya jawab' in prose"),
    (re.compile(r"\bself-verification\b", re.IGNORECASE), "prefer 'verifikasi mandiri' in prose"),
)

ENGLISH_FUNCTION_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "use",
    "using",
    "when",
    "with",
    "you",
    "your",
}
INDONESIAN_FUNCTION_WORDS = {
    "agar",
    "akan",
    "atau",
    "dalam",
    "dan",
    "dari",
    "dengan",
    "di",
    "ini",
    "itu",
    "jika",
    "ke",
    "pada",
    "sebagai",
    "untuk",
    "yang",
}


class DuplicateKeyError(ValueError):
    """Raised when a JSON object contains a duplicate key."""

    def __init__(self, key: str) -> None:
        super().__init__(f"duplicate JSON key: {key}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


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
            print(" PASS: 0 errors, 0 warnings")
        elif not self.errors:
            print(f" PASS: 0 errors, {len(self.warnings)} warning(s)")


def load_json_object(path: Path, report: Report, *, role: str) -> dict[str, Any] | None:
    if not path.exists():
        report.error("-", f"{role} file is missing: {path}")
        return None
    if not path.is_file():
        report.error("-", f"{role} path is not a file: {path}")
        return None

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.error("-", f"cannot read {role} file {path}: {exc}")
        return None
    except UnicodeDecodeError as exc:
        report.error("-", f"{role} file is not valid UTF-8: {exc}")
        return None

    try:
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateKeyError as exc:
        report.error("-", f"{role} JSON contains {exc}")
        return None
    except json.JSONDecodeError as exc:
        report.error(
            "-",
            f"{role} JSON is invalid at line {exc.lineno}, column {exc.colno}: {exc.msg}",
        )
        return None

    if not isinstance(data, dict):
        report.error("-", f"{role} JSON root must be an object")
        return None

    # JSON object keys are strings by specification. Keep the explicit check so
    # future parser/refactor changes still fail safely.
    for key, value in data.items():
        if not isinstance(key, str):
            report.error(repr(key), f"{role} key is not a string")
        if not isinstance(value, str):
            report.error(str(key), f"{role} value is not a string ({type(value).__name__})")

    return data


def backend_expected_keys(en: dict[str, Any]) -> list[str]:
    """Return backend keys translated by the established locale convention."""
    keys: list[str] = []
    for key in en:
        if BACKEND_NAME_KEY.match(key):
            continue
        if key.startswith("components."):
            parts = key.split(".")
            if len(parts) >= BACKEND_KEY_MIN_PARTS and parts[-2] in ("description", "info", "placeholder"):
                keys.append(key)
        elif key.startswith(("starter_flows.", "template_notes.")):
            keys.append(key)
    return keys


def _matches(pattern: re.Pattern[str], text: str) -> Counter[str]:
    return Counter(match.group(0) for match in pattern.finditer(text))


def _captured(pattern: re.Pattern[str], text: str) -> Counter[str]:
    return Counter(match.group(1) for match in pattern.finditer(text))


def _urls(text: str) -> Counter[str]:
    return Counter(match.group(0).rstrip(".,;:!?)'\"") for match in URL.finditer(text))


def _markdown_link_destinations(text: str) -> list[str]:
    return [match.group(2) for match in MARKDOWN_LINK.finditer(text)]


def tag_order_error(value: str) -> str | None:
    """Return why numbered tags are malformed, or None when properly nested."""
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


def _compare_counter(
    report: Report,
    key: str,
    name: str,
    expected: Counter[str],
    actual: Counter[str],
) -> None:
    if expected == actual:
        return
    missing = sorted((expected - actual).elements())
    added = sorted((actual - expected).elements())
    report.error(key, f"{name} mismatch: missing {missing}, unexpected {added}")


def _looks_like_english_prose(value: str) -> bool:
    # Remove structures intentionally expected to remain English before scoring.
    stripped = URL.sub(" ", value)
    stripped = INLINE_CODE.sub(" ", stripped)
    stripped = FENCED_CODE.sub(" ", stripped)
    words = [word.lower() for word in ASCII_WORD.findall(stripped)]
    if len(words) < ENGLISH_PROSE_MIN_WORDS:
        return False
    english_hits = sum(word in ENGLISH_FUNCTION_WORDS for word in words)
    indonesian_hits = sum(word in INDONESIAN_FUNCTION_WORDS for word in words)
    return (
        english_hits >= ENGLISH_PROSE_MIN_FUNCTION_WORDS
        and english_hits >= indonesian_hits + ENGLISH_PROSE_DOMINANCE_MARGIN
    )


def _warn_language_quality(report: Report, key: str, en_value: str, id_value: str) -> None:
    english_words = ASCII_WORD.findall(en_value)
    if (
        id_value == en_value
        and len(english_words) >= UNTRANSLATED_MIN_WORDS
        and URL.fullmatch(id_value.strip()) is None
    ):
        report.warn(key, f"looks untranslated (identical to English) | {id_value[:80]}")
    elif _looks_like_english_prose(id_value):
        report.warn(key, f"contains a long English-looking prose segment | {id_value[:80]}")

    for term, source_pattern, translated_pattern in PROTECTED_TERM_WARNINGS:
        if source_pattern.search(en_value) and not source_pattern.search(id_value):
            found = translated_pattern.search(id_value)
            if found:
                report.warn(
                    key,
                    f"terminology: source uses protected term {term!r}, "
                    f"but translation contains {found.group(0)!r}; review context",
                )

    for pattern, why in SUSPICIOUS_INDONESIAN:
        found = pattern.search(id_value)
        if found:
            report.warn(key, f"suspicious wording {found.group(0)!r}: {why}")


def check_value(
    report: Report,
    key: str,
    en_value: Any,
    id_value: Any,
    *,
    markdown: bool,
    label_check: bool,
) -> None:
    if not isinstance(en_value, str):
        # The source loader has already reported this; avoid cascading crashes.
        return
    if not isinstance(id_value, str):
        # The locale loader has already reported this.
        return
    if not id_value.strip():
        report.error(key, "empty value (would fall back to English)")
        return

    _compare_counter(report, key, "{{variable}}", _captured(I18N_VAR, en_value), _captured(I18N_VAR, id_value))
    _compare_counter(report, key, "{placeholder}", _captured(PY_VAR, en_value), _captured(PY_VAR, id_value))
    _compare_counter(report, key, "${expression}", _captured(DOLLAR_VAR, en_value), _captured(DOLLAR_VAR, id_value))
    _compare_counter(report, key, "printf placeholder", _matches(PRINTF_VAR, en_value), _matches(PRINTF_VAR, id_value))
    _compare_counter(report, key, "<n> tag", _matches(TAG, en_value), _matches(TAG, id_value))
    _compare_counter(report, key, "URL", _urls(en_value), _urls(id_value))

    malformed = tag_order_error(id_value)
    if malformed:
        report.error(key, f"<n> tags out of order: {malformed}")

    # Environment-variable-like identifiers are safe to preserve mechanically
    # because the pattern requires at least one underscore.
    _compare_counter(
        report,
        key,
        "environment variable / constant",
        _matches(ENV_VAR, en_value),
        _matches(ENV_VAR, id_value),
    )

    if markdown:
        for marker, name in (
            (r"(?m)^#{1,6} ", "heading"),
            (r"(?m)^\s*(?:[-*]|\d+\.) ", "list item"),
            (r"```", "code fence"),
            (r"\]\(", "link"),
        ):
            if len(re.findall(marker, en_value)) != len(re.findall(marker, id_value)):
                report.error(key, f"Markdown {name} count differs from the English note")

        en_link_destinations = _markdown_link_destinations(en_value)
        id_link_destinations = _markdown_link_destinations(id_value)
        if en_link_destinations != id_link_destinations and Counter(en_link_destinations) == Counter(
            id_link_destinations
        ):
            report.error(
                key,
                "Markdown link destinations are reordered relative to the English note",
            )

        if en_value.count("**") != id_value.count("**"):
            report.error(key, "Markdown bold-marker count differs from the English note")
        if id_value.count("**") % 2:
            report.error(key, "unbalanced ** bold markers")

        _compare_counter(
            report,
            key,
            "inline code",
            _captured(INLINE_CODE, en_value),
            _captured(INLINE_CODE, id_value),
        )
        _compare_counter(
            report,
            key,
            "fenced code block",
            _captured(FENCED_CODE, en_value),
            _captured(FENCED_CODE, id_value),
        )

    _warn_language_quality(report, key, en_value, id_value)

    if (
        label_check
        and "\n" not in en_value
        and len(en_value) <= SHORT_LABEL_CHARS
        and not URL.search(en_value)
        and not I18N_VAR.search(en_value)
        and len(id_value) > (2.6 * max(len(en_value), 1) + 8)
    ):
        report.warn(
            key,
            f"short label expanded substantially ({len(en_value)} -> {len(id_value)} chars) | {id_value}",
        )


def _warn_inconsistent_translations(
    report: Report,
    english_to_indonesian: dict[str, set[str]],
) -> None:
    for english, translations in english_to_indonesian.items():
        if len(translations) > 1:
            samples = sorted(translations)
            preview = "; ".join(repr(item[:45]) for item in samples[:INCONSISTENT_TRANSLATION_PREVIEW_LIMIT])
            if len(samples) > INCONSISTENT_TRANSLATION_PREVIEW_LIMIT:
                preview += "; ..."
            report.warn(
                "-",
                f"same English source has {len(translations)} Indonesian translations: {english[:60]!r} -> {preview}",
            )


def check_frontend(id_path: Path, *, partial: bool, max_lines: int) -> tuple[int, int]:
    report = Report(f"frontend: {id_path}")

    en = load_json_object(FRONTEND_DIR / "en.json", report, role="frontend English source")
    id_data = load_json_object(id_path, report, role="frontend Indonesian locale")

    if en is None or id_data is None:
        report.print(max_lines)
        return len(report.errors), len(report.warnings)

    report.title = f"frontend: {id_path}  ({len(id_data)}/{len(en)} keys)"

    if not partial:
        for key in en:
            if key not in id_data:
                report.error(key, "missing frontend key")
        for key in id_data:
            if key not in en:
                report.error(key, "unexpected frontend key")
        if [key for key in id_data if key in en] != [key for key in en if key in id_data]:
            report.warn("-", "key order differs from en.json")

    by_english: dict[str, set[str]] = defaultdict(set)

    for key, value in id_data.items():
        if key not in en:
            if partial:
                report.error(key, "unexpected frontend key (not in en.json)")
            continue

        check_value(report, key, en[key], value, markdown=False, label_check=True)

        if isinstance(en[key], str) and isinstance(value, str):
            by_english[en[key]].add(value)

    if not partial:
        for key in id_data:
            for suffix, twin in (("_one", "_other"), ("_other", "_one")):
                if key.endswith(suffix):
                    twin_key = key[: -len(suffix)] + twin
                    if twin_key in en and twin_key not in id_data:
                        report.error(key, f"plural twin {twin_key} is missing")

    _warn_inconsistent_translations(report, by_english)
    report.print(max_lines)
    return len(report.errors), len(report.warnings)


def check_backend(id_path: Path, *, partial: bool, max_lines: int) -> tuple[int, int]:
    report = Report(f"backend: {id_path}")

    en = load_json_object(BACKEND_DIR / "en.json", report, role="backend English source")
    id_data = load_json_object(id_path, report, role="backend Indonesian locale")

    if en is None or id_data is None:
        report.print(max_lines)
        return len(report.errors), len(report.warnings)

    expected = backend_expected_keys(en)
    expected_set = set(expected)
    report.title = f"backend: {id_path}  ({len(id_data)}/{len(expected)} intended keys)"

    if not partial:
        for key in expected:
            if key not in id_data:
                report.error(key, "missing intended backend key")
        for key in id_data:
            if key not in expected_set:
                if key not in en:
                    report.error(
                        key,
                        "unexpected backend key (not in en.json; backend keys include an English-text hash)",
                    )
                elif BACKEND_NAME_KEY.match(key):
                    report.error(
                        key,
                        "name/display-name key must be omitted so the English name shows through",
                    )
                else:
                    report.error(
                        key,
                        "unexpected backend key outside the established translatable subset",
                    )

        if [key for key in id_data if key in expected_set] != [key for key in expected if key in id_data]:
            report.warn("-", "translatable backend key order differs from en.json")
    else:
        for key in id_data:
            if key not in en:
                report.error(
                    key,
                    "unexpected backend key (not in en.json; backend keys include an English-text hash)",
                )
            elif key not in expected_set:
                if BACKEND_NAME_KEY.match(key):
                    report.error(
                        key,
                        "name/display-name key must be omitted so the English name shows through",
                    )
                else:
                    report.error(
                        key,
                        "backend key is outside the established translatable subset",
                    )

    by_english: dict[str, set[str]] = defaultdict(set)

    for key, value in id_data.items():
        if key not in expected_set or key not in en:
            continue

        check_value(
            report,
            key,
            en[key],
            value,
            markdown=key.startswith("template_notes."),
            label_check=False,
        )

        if isinstance(en[key], str) and isinstance(value, str):
            by_english[en[key]].add(value)

    _warn_inconsistent_translations(report, by_english)
    report.print(max_lines)
    return len(report.errors), len(report.warnings)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--only",
        choices=("frontend", "backend"),
        help="check one complete Indonesian locale file only",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="check a partial translation file instead of the repository id.json",
    )
    parser.add_argument(
        "--against",
        choices=("frontend", "backend"),
        help="which English catalog a --file belongs to",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=40,
        help="diagnostic lines to print per section, 0 for all",
    )
    args = parser.parse_args()

    if args.max < 0:
        parser.error("--max must be 0 or greater")
    if args.file and args.only:
        parser.error("--file cannot be combined with --only")
    if args.against and not args.file:
        parser.error("--against requires --file")
    if args.file and not args.against:
        parser.error("--file needs --against frontend|backend")

    max_lines = args.max or 10**9

    if args.file:
        checker = check_frontend if args.against == "frontend" else check_backend
        errors, warnings = checker(args.file, partial=True, max_lines=max_lines)
        print(f"\n{'FAILED' if errors else 'PASSED'}: {errors} error(s), {warnings} warning(s)")
        raise SystemExit(1 if errors else 0)

    total_errors = 0
    total_warnings = 0

    checks = (
        ("frontend", FRONTEND_DIR / "id.json", check_frontend),
        ("backend", BACKEND_DIR / "id.json", check_backend),
    )
    for name, path, checker in checks:
        if args.only and args.only != name:
            continue
        errors, warnings = checker(path, partial=False, max_lines=max_lines)
        total_errors += errors
        total_warnings += warnings

    print(f"\n{'FAILED' if total_errors else 'PASSED'}: {total_errors} error(s), {total_warnings} warning(s)")
    raise SystemExit(1 if total_errors else 0)


if __name__ == "__main__":
    main()
