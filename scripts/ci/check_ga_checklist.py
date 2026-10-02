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

# The release gates only a human can close. They are not ticket acceptance areas,
# so they stay out of REQUIRED_ITEMS, but a checklist that loses one of these rows
# reads as fully validated. Sign-off flips the row to ``validated`` with evidence;
# it never deletes it.
REQUIRED_SIGNOFF_GATES = frozenset(
    {
        "live-tenant-consent",
        "connections-ui-a11y-i18n",
    }
)


def _evidence_path_error(entry: str) -> str | None:
    """Return why ``entry`` is unusable as evidence, or ``None`` when it is fine.

    Evidence must name something that lives in this repository. An absolute
    path would discard ``REPO_ROOT`` on join and let the record claim a CI
    runner's filesystem as GA evidence (``"/"`` always exists); a ``..`` path
    would do the same by escaping upward.
    """
    # Allow ``path::test_name`` selectors; only the path part must resolve.
    raw = entry.split("::", 1)[0]
    if not raw:
        return f"evidence entry has an empty path: {entry}"
    candidate = Path(raw)
    if candidate.is_absolute():
        return f"evidence path must be repository-relative, not absolute: {entry}"
    resolved = (REPO_ROOT / candidate).resolve()
    if REPO_ROOT not in resolved.parents:
        return f"evidence path is outside the repository: {entry}"
    if not resolved.exists():
        return f"evidence path does not exist: {entry}"
    return None


def _validate_item(item: object, index: int, errors: list[str]) -> None:
    """Append every structural problem found in one acceptance item to `errors`."""
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
        # Membership against a frozenset raises TypeError on an unhashable
        # value, so reject non-string entries before testing them.
        if any(not isinstance(c, str) for c in contexts):
            errors.append(f"{prefix} ({item_id}): 'contexts' entries must be strings")
        unknown = sorted({c for c in contexts if isinstance(c, str) and c not in VALID_CONTEXTS})
        if unknown:
            errors.append(f"{prefix} ({item_id}): unknown contexts {unknown}")

    status = item.get("status")
    # Membership against a frozenset hashes the value, so an object or array
    # status would raise TypeError instead of being reported.
    if not isinstance(status, str) or status not in VALID_STATUSES:
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
                path_error = _evidence_path_error(entry)
                if path_error:
                    errors.append(f"{prefix} ({item_id}): {path_error}")
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
            if not isinstance(c_status, str) or c_status not in VALID_STATUSES:
                errors.append(f"contexts/{context}: status must be one of {sorted(VALID_STATUSES)}")
            if c_status == "validated" and not entry.get("evidence"):
                errors.append(f"contexts/{context}: validated context must list evidence")
            if c_status == "pending-signoff":
                pending = entry.get("pending")
                if not isinstance(pending, dict) or not pending.get("owner") or not pending.get("reason"):
                    errors.append(f"contexts/{context}: pending-signoff context needs pending.owner and pending.reason")
            context_evidence = entry.get("evidence")
            if context_evidence is not None and not isinstance(context_evidence, list):
                # A bare string would otherwise iterate character by character.
                errors.append(f"contexts/{context}: 'evidence' must be a list")
                context_evidence = []
            for evidence_entry in context_evidence or []:
                if not isinstance(evidence_entry, str) or not evidence_entry:
                    errors.append(f"contexts/{context}: evidence entries must be non-empty strings")
                    continue
                path_error = _evidence_path_error(evidence_entry)
                if path_error:
                    errors.append(f"contexts/{context}: {path_error}")

    items = checklist.get("items")
    if not isinstance(items, list) or not items:
        errors.append("top-level 'items' must be a non-empty list")
        return errors

    # Only string ids participate: an object id is unhashable and a mixed-type
    # set is unsortable, and ``_validate_item`` already reports the bad id.
    ids = [item.get("id") for item in items if isinstance(item, dict)]
    string_ids = [i for i in ids if isinstance(i, str) and i]
    duplicates = sorted({i for i in string_ids if string_ids.count(i) > 1})
    if duplicates:
        errors.append(f"duplicate item ids: {duplicates}")

    missing_items = sorted(REQUIRED_ITEMS - set(string_ids))
    if missing_items:
        errors.append(f"checklist is missing required acceptance items: {missing_items}")

    missing_gates = sorted(REQUIRED_SIGNOFF_GATES - set(string_ids))
    if missing_gates:
        errors.append(f"checklist is missing required release sign-off gates: {missing_gates}")

    for index, item in enumerate(items):
        _validate_item(item, index, errors)

    return errors


def main() -> int:
    """Validate the checklist named on the command line; return the process exit code."""
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
