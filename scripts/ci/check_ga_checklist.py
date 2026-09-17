#!/usr/bin/env python3
"""Validate the Dedicated Integrations GA checklist (INT-14).

``design/dedicated-integrations/ga-checklist.json`` is the INT-14 record: one
entry per GA acceptance item, each mapped to machine-checkable evidence (test
files, docs pages, CI workflows) or to an explicit ``pending-signoff`` block for
the parts only a human can complete (live tenant validation, release-owner
signature). This checker proves the record stays honest: every claimed evidence
path must exist, every item must carry a status, and pending items must name an
owner and a reason so they cannot be silently treated as done.

The checker is structural. It proves the evidence pointers are real; it does not
re-run the referenced tests. Run it directly or through
``scripts/ci/test_ga_checklist.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_ROOT = REPO_ROOT / "design" / "dedicated-integrations"
DEFAULT_CHECKLIST = DESIGN_ROOT / "ga-checklist.json"

REQUIRED_CONTEXTS = frozenset({"hosted", "self_managed", "desktop"})
VALID_CONTEXTS = REQUIRED_CONTEXTS | {"headless"}
VALID_STATUSES = frozenset({"validated", "pending-signoff"})

# The acceptance areas from the INT-14 ticket. Every one must appear exactly
# once so an area cannot be dropped from the record without a CI failure.
REQUIRED_ITEMS = frozenset(
    {
        "stable-schemas",
        "least-privilege-scopes",
        "secret-redaction",
        "revocation-refresh",
        "policy-enforcement",
        "rate-limit-handling",
        "install-upgrade",
        "unavailable-incompatible-tools",
        "callback-paths-client-types",
        "security-review",
        "documentation",
        "accessibility",
        "i18n",
    }
)


def _validate_item(item: object, index: int, errors: list[str]) -> None:
    prefix = f"items/{index}"
    if not isinstance(item, dict):
        errors.append(f"{prefix}: item is not an object")
        return
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id:
        errors.append(f"{prefix}: missing or empty 'id'")
        item_id = f"#{index}"
    if not isinstance(item.get("title"), str) or not item["title"]:
        errors.append(f"{prefix} ({item_id}): missing or empty 'title'")

    contexts = item.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        errors.append(f"{prefix} ({item_id}): 'contexts' must be a non-empty list")
    else:
        unknown = sorted({c for c in contexts if c not in VALID_CONTEXTS})
        if unknown:
            errors.append(f"{prefix} ({item_id}): unknown contexts {unknown}")

    status = item.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"{prefix} ({item_id}): status must be one of {sorted(VALID_STATUSES)}")
        return

    if status == "validated":
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix} ({item_id}): validated item must list at least one evidence path")
        else:
            for entry in evidence:
                if not isinstance(entry, str) or not entry:
                    errors.append(f"{prefix} ({item_id}): evidence entries must be non-empty strings")
                    continue
                # Allow ``path::test_name`` selectors; only the path must exist.
                path = REPO_ROOT / entry.split("::", 1)[0]
                if not path.exists():
                    errors.append(f"{prefix} ({item_id}): evidence path does not exist: {entry}")
        if "pending" in item or "signoff" in item:
            errors.append(f"{prefix} ({item_id}): validated item must not carry a pending-signoff block")
    else:
        pending = item.get("pending")
        if not isinstance(pending, dict):
            errors.append(f"{prefix} ({item_id}): pending-signoff item must carry a 'pending' object")
        else:
            errors.extend(
                f"{prefix} ({item_id}): pending.{field} is required for pending-signoff items"
                for field in ("owner", "reason")
                if not isinstance(pending.get(field), str) or not pending[field]
            )
        if item.get("evidence"):
            errors.append(f"{prefix} ({item_id}): pending-signoff item must not claim evidence")


def validate_checklist(path: Path) -> list[str]:
    """Return a list of validation errors for the GA checklist at ``path``."""
    try:
        checklist = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"could not read GA checklist {path}: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"GA checklist {path} is not valid JSON: {exc}"]

    errors: list[str] = []
    if not isinstance(checklist, dict):
        return [f"GA checklist {path}: top level must be an object"]

    if checklist.get("ticket") != "INT-14":
        errors.append("top-level 'ticket' must be 'INT-14'")

    contexts = checklist.get("contexts")
    if not isinstance(contexts, dict):
        errors.append("top-level 'contexts' must be an object keyed by deployment context")
    else:
        missing_contexts = sorted(REQUIRED_CONTEXTS - set(contexts))
        if missing_contexts:
            errors.append(f"checklist is missing required context checklists: {missing_contexts}")
        for context, entry in contexts.items():
            if context not in VALID_CONTEXTS:
                errors.append(f"unknown deployment context '{context}'")
                continue
            if not isinstance(entry, dict):
                errors.append(f"contexts/{context}: entry must be an object")
                continue
            c_status = entry.get("status")
            if c_status not in VALID_STATUSES:
                errors.append(f"contexts/{context}: status must be one of {sorted(VALID_STATUSES)}")
            if c_status == "validated" and not entry.get("evidence"):
                errors.append(f"contexts/{context}: validated context must list evidence")
            if c_status == "pending-signoff":
                pending = entry.get("pending")
                if not isinstance(pending, dict) or not pending.get("owner") or not pending.get("reason"):
                    errors.append(f"contexts/{context}: pending-signoff context needs pending.owner and pending.reason")
            for evidence_entry in entry.get("evidence") or []:
                evidence_path = REPO_ROOT / str(evidence_entry).split("::", 1)[0]
                if not evidence_path.exists():
                    errors.append(f"contexts/{context}: evidence path does not exist: {evidence_entry}")

    items = checklist.get("items")
    if not isinstance(items, list) or not items:
        errors.append("top-level 'items' must be a non-empty list")
        return errors

    ids: list[object] = [item.get("id") if isinstance(item, dict) else None for item in items]
    duplicates = sorted({i for i in ids if i is not None and ids.count(i) > 1})
    if duplicates:
        errors.append(f"duplicate item ids: {duplicates}")

    missing_items = sorted(REQUIRED_ITEMS - {i for i in ids if isinstance(i, str)})
    if missing_items:
        errors.append(f"checklist is missing required acceptance items: {missing_items}")

    for index, item in enumerate(items):
        _validate_item(item, index, errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checklist", type=Path, default=DEFAULT_CHECKLIST)
    args = parser.parse_args()

    errors = validate_checklist(args.checklist)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"GA checklist OK: {args.checklist}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
