"""Check that translated locale files stay aligned with en.json.

en.json is the source of truth: it is regenerated from component code by
extract_backend_strings.py and uploaded to GP, and GP translations are
downloaded back into the per-language files. The invariant we guard:

  * orphan keys  = keys present in a <lang>.json but NOT in en.json.
    These will be pruned on the next GP download cycle. A *handful* is normal
    churn (a component string changed, so its hash — and key — changed, and the
    old translated key lingers until the next sync). A *flood* means en.json
    lost keys it should still have — exactly the regression that happened when
    the bundle mass-extraction left extract_backend_strings.py walking only
    lfx.components, so every extracted component silently dropped out of en.json
    while its ~30k translations sat orphaned in the other languages.

  * missing keys = keys in en.json but NOT in a <lang>.json. These are simply
    untranslated and fall back to English at runtime, so they are reported but
    never fail the check.

This is a backstop for *mass* regressions, not a strict equality gate — the GP
download cycle is what drives the files to zero orphans. Run it after
extract_backend_strings.py (en.json fresh) for the most meaningful result.

Usage:
    python scripts/gp/check_locale_alignment.py                 # backend, default threshold
    python scripts/gp/check_locale_alignment.py --target frontend
    python scripts/gp/check_locale_alignment.py --max-orphans 50
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
LOCALES_DIRS = {
    "backend": _REPO_ROOT / "src/backend/base/langflow/locales",
    "frontend": _REPO_ROOT / "src/frontend/src/locales",
}
# A flood of orphans means en.json lost keys it should still have. Normal churn
# (a few changed strings between GP sync cycles) stays well under this.
DEFAULT_MAX_ORPHANS = 200


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def check_alignment(locales_dir: Path, max_orphans: int) -> int:
    """Print an alignment report and return the number of languages over budget."""
    en_path = locales_dir / "en.json"
    if not en_path.exists():
        print(f"ERROR: {en_path} does not exist.")
        return 1
    en_keys = set(_load(en_path))
    print(f"en.json: {len(en_keys)} keys  (source of truth)\n")
    print(f"{'lang':10} {'keys':>7} {'orphan (→pruned)':>18} {'missing (→English)':>20}")

    over_budget = 0
    for path in sorted(locales_dir.glob("*.json")):
        lang = path.stem
        if lang == "en":
            continue
        keys = set(_load(path))
        orphan = len(keys - en_keys)
        missing = len(en_keys - keys)
        flag = "  <-- OVER BUDGET" if orphan > max_orphans else ""
        print(f"{lang:10} {len(keys):7d} {orphan:18d} {missing:20d}{flag}")
        if orphan > max_orphans:
            over_budget += 1

    if over_budget:
        print(
            f"\nFAIL: {over_budget} language(s) exceed the orphan budget ({max_orphans}). "
            "en.json likely lost keys it should still contain — re-run "
            "extract_backend_strings.py and confirm all bundles imported."
        )
    else:
        print(f"\nOK: all languages within the orphan budget ({max_orphans}).")
    return over_budget


def main() -> None:
    parser = argparse.ArgumentParser(description="Check translated locales stay aligned with en.json")
    parser.add_argument("--target", choices=["backend", "frontend"], default="backend")
    parser.add_argument("--locales-dir", help="Override the locales directory to check")
    parser.add_argument(
        "--max-orphans",
        type=int,
        default=DEFAULT_MAX_ORPHANS,
        help=f"Fail if any language has more than this many orphan keys (default {DEFAULT_MAX_ORPHANS})",
    )
    args = parser.parse_args()

    locales_dir = Path(args.locales_dir) if args.locales_dir else LOCALES_DIRS[args.target]
    sys.exit(1 if check_alignment(locales_dir, args.max_orphans) else 0)


if __name__ == "__main__":
    main()
