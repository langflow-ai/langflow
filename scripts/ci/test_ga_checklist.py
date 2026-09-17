from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_ga_checklist import (
    DEFAULT_CHECKLIST,
    REQUIRED_CONTEXTS,
    REQUIRED_ITEMS,
    validate_checklist,
)

CI_SCRIPTS_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci-scripts-test.yml"


def _workflow_pull_request_paths() -> list[str]:
    """Read the quoted pull-request path filters without adding a YAML dependency."""
    workflow = CI_SCRIPTS_WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count("    paths:\n") == 1, "expected exactly one pull-request paths block"
    assert "  workflow_dispatch:" in workflow, "expected workflow_dispatch to terminate the paths block"
    paths_block = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
    entries = [line.strip().removeprefix("- ") for line in paths_block.splitlines() if line.strip()]
    return [json.loads(entry) for entry in entries]


def _github_path_matches(path: str, pattern: str) -> bool:
    """Match the ``*`` and ``**`` forms used by this workflow's path filters."""
    regex_parts: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern[index : index + 2] == "**":
            regex_parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            regex_parts.append("[^/]*")
            index += 1
        else:
            regex_parts.append(re.escape(pattern[index]))
            index += 1
    return re.fullmatch("".join(regex_parts), path) is not None


def _load() -> dict:
    """Read the committed checklist as a dict the tests can mutate per case."""
    return json.loads(DEFAULT_CHECKLIST.read_text(encoding="utf-8"))


def _write(tmp_path: Path, checklist: dict) -> Path:
    """Write a mutated checklist to a temp path and return it for the checker."""
    path = tmp_path / "ga-checklist.json"
    path.write_text(json.dumps(checklist), encoding="utf-8")
    return path


def test_ga_checklist_is_valid() -> None:
    """The checklist committed to the repo passes the checker as-is."""
    assert validate_checklist(DEFAULT_CHECKLIST) == []


def test_every_required_acceptance_item_is_present() -> None:
    """No acceptance item may be dropped from the checklist without failing this gate."""
    checklist = _load()
    ids = {item["id"] for item in checklist["items"]}
    assert set(REQUIRED_ITEMS) <= ids


def test_every_required_context_has_a_checklist() -> None:
    """Each GA context the feature ships in carries its own status block."""
    checklist = _load()
    assert set(REQUIRED_CONTEXTS) <= set(checklist["contexts"])


def test_ci_workflow_watches_the_checklist_and_checker() -> None:
    """Editing the checklist or the checker must trigger the workflow that validates them."""
    workflow_paths = _workflow_pull_request_paths()
    canonical_paths = [
        "design/dedicated-integrations/ga-checklist.json",
        "scripts/ci/check_ga_checklist.py",
    ]
    uncovered = [
        path for path in canonical_paths if not any(_github_path_matches(path, pattern) for pattern in workflow_paths)
    ]
    assert uncovered == [], f"CI scripts checker is not triggered by GA checklist paths: {uncovered}"


def test_checker_rejects_missing_acceptance_item(tmp_path: Path) -> None:
    """A checklist that silently drops an acceptance item is rejected."""
    checklist = _load()
    checklist["items"] = [item for item in checklist["items"] if item["id"] != "secret-redaction"]

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("secret-redaction" in error for error in errors)


def test_checker_rejects_missing_context(tmp_path: Path) -> None:
    """A checklist that omits a required context is rejected."""
    checklist = _load()
    checklist["contexts"].pop("desktop")

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("desktop" in error for error in errors)


def test_checker_rejects_validated_item_without_evidence(tmp_path: Path) -> None:
    """`validated` is only claimable with evidence attached."""
    checklist = _load()
    item = next(item for item in checklist["items"] if item["status"] == "validated")
    item["evidence"] = []

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any(item["id"] in error and "evidence" in error for error in errors)


def test_checker_rejects_evidence_path_that_does_not_exist(tmp_path: Path) -> None:
    """Evidence must name a path that exists in the tree being validated."""
    checklist = _load()
    item = next(item for item in checklist["items"] if item["status"] == "validated")
    item["evidence"] = ["src/backend/tests/unit/api/v1/test_does_not_exist.py"]

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("does not exist" in error and "test_does_not_exist.py" in error for error in errors)


def test_checker_rejects_pending_item_without_owner(tmp_path: Path) -> None:
    """A `pending-signoff` item must name the human who owes the signature."""
    checklist = _load()
    pending_ids = [item["id"] for item in checklist["items"] if item["status"] == "pending-signoff"]
    assert pending_ids, "fixture needs at least one pending-signoff item"
    item = next(item for item in checklist["items"] if item["id"] == pending_ids[0])
    item["pending"] = {"reason": "Awaiting live validation."}

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("pending.owner" in error for error in errors)


def test_checker_rejects_pending_item_claiming_evidence(tmp_path: Path) -> None:
    """A pending item may not also claim evidence: that is a validated item mislabeled."""
    checklist = _load()
    item = next(item for item in checklist["items"] if item["status"] == "pending-signoff")
    item["evidence"] = ["design/dedicated-integrations/README.md"]

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("must not claim evidence" in error for error in errors)


def test_checker_rejects_duplicate_item_ids(tmp_path: Path) -> None:
    """Duplicate ids would let one item's evidence stand in for another's."""
    checklist = _load()
    checklist["items"].append(dict(checklist["items"][0]))

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("duplicate item ids" in error for error in errors)


def test_checker_rejects_unknown_status(tmp_path: Path) -> None:
    """Only the known status vocabulary is accepted."""
    checklist = _load()
    checklist["items"][0]["status"] = "done"

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("status must be one of" in error for error in errors)


def test_checker_reports_malformed_json(tmp_path: Path) -> None:
    """A checklist that is not JSON fails with a message rather than a traceback."""
    path = tmp_path / "ga-checklist.json"
    path.write_text("{not-json", encoding="utf-8")

    errors = validate_checklist(path)

    assert len(errors) == 1
    assert "is not valid JSON" in errors[0]


def test_checker_reports_missing_file(tmp_path: Path) -> None:
    """A missing checklist fails the gate instead of passing vacuously."""
    missing = tmp_path / "ga-checklist.json"

    errors = validate_checklist(missing)

    assert len(errors) == 1
    assert "could not read GA checklist" in errors[0]


def test_checker_rejects_absolute_evidence_path(tmp_path: Path) -> None:
    """``/`` always exists: joining it onto REPO_ROOT would pass the existence check."""
    checklist = _load()
    item = next(item for item in checklist["items"] if item["status"] == "validated")
    item["evidence"] = ["/"]

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("not absolute" in error for error in errors)


def test_checker_rejects_evidence_path_escaping_the_repository(tmp_path: Path) -> None:
    """`..` in an evidence path cannot reach outside the repository."""
    checklist = _load()
    item = next(item for item in checklist["items"] if item["status"] == "validated")
    item["evidence"] = ["../../../etc/hosts"]

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("outside the repository" in error for error in errors)


def test_checker_rejects_repository_root_as_evidence(tmp_path: Path) -> None:
    """The repository root is not evidence for anything."""
    checklist = _load()
    item = next(item for item in checklist["items"] if item["status"] == "validated")
    item["evidence"] = ["."]

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("outside the repository" in error for error in errors)


def test_checker_rejects_absolute_context_evidence_path(tmp_path: Path) -> None:
    """A context's evidence is held to the same in-repo rule as an item's."""
    checklist = _load()
    context = next(
        entry
        for entry in checklist["contexts"].values()
        if entry.get("status") == "validated" and entry.get("evidence")
    )
    context["evidence"] = ["/"]

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("not absolute" in error for error in errors)


def test_checker_rejects_non_list_context_evidence(tmp_path: Path) -> None:
    """A bare string would otherwise be iterated one character at a time."""
    checklist = _load()
    context_name, context = next(
        (name, entry) for name, entry in checklist["contexts"].items() if entry.get("evidence")
    )
    context["evidence"] = "design/dedicated-integrations/README.md"

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any(f"contexts/{context_name}: 'evidence' must be a list" == error for error in errors)


def test_checker_reports_object_valued_contexts_instead_of_raising(tmp_path: Path) -> None:
    """Frozenset membership raises TypeError on an unhashable value."""
    checklist = _load()
    checklist["items"][0]["contexts"] = [{"hosted": True}]

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("'contexts' entries must be strings" in error for error in errors)


def test_checker_reports_object_valued_item_id_instead_of_raising(tmp_path: Path) -> None:
    """A repeated object id reaches the duplicate-id set comprehension, which hashes it."""
    checklist = _load()
    checklist["items"][0]["id"] = {"id": "stable-schemas"}
    checklist["items"].append(dict(checklist["items"][0]))

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("missing or empty 'id'" in error for error in errors)


def test_checker_reports_mixed_type_item_ids_instead_of_raising(tmp_path: Path) -> None:
    """Sorting a set holding both an int and a str id would raise TypeError."""
    checklist = _load()
    checklist["items"][0]["id"] = 7
    checklist["items"].append(dict(checklist["items"][0]))
    checklist["items"].append(dict(checklist["items"][1]))

    errors = validate_checklist(_write(tmp_path, checklist))

    assert any("missing or empty 'id'" in error for error in errors)
    assert [error for error in errors if "duplicate item ids" in error] == [
        f"duplicate item ids: ['{checklist['items'][1]['id']}']"
    ]
