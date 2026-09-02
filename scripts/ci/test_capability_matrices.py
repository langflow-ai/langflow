from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_capability_matrices import (
    DEFAULT_MATRIX_DIR,
    DESIGN_ROOT,
    REQUIRED_PROVIDERS,
    SCHEMA_PATH,
    VALID_VALUES,
    validate_all,
    validate_matrix,
)

CI_SCRIPTS_WORKFLOW = DESIGN_ROOT.parents[1] / ".github" / "workflows" / "ci-scripts-test.yml"


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


def _copy_design(tmp_path: Path) -> Path:
    """Copy the matrices and decision records so a test can corrupt them without touching the repo."""
    root = tmp_path / "dedicated-integrations"
    shutil.copytree(DESIGN_ROOT / "matrices", root / "matrices")
    shutil.copytree(DESIGN_ROOT / "decisions", root / "decisions")
    return root


def _load(root: Path, provider: str) -> dict:
    return json.loads((root / "matrices" / f"{provider}.json").read_text(encoding="utf-8"))


def _save(root: Path, provider: str, matrix: dict) -> Path:
    path = root / "matrices" / f"{provider}.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")
    return path


def test_capability_matrices_are_complete() -> None:
    assert validate_all() == []


def test_every_required_provider_has_a_matrix() -> None:
    present = {path.stem for path in DEFAULT_MATRIX_DIR.glob("*.json")}
    assert present == set(REQUIRED_PROVIDERS)


def test_ci_workflow_watches_design_directory_and_checker() -> None:
    workflow_paths = _workflow_pull_request_paths()
    canonical_paths = [
        "design/dedicated-integrations/matrices/google.json",
        "design/dedicated-integrations/decisions/substrate-google.md",
        "scripts/ci/check_capability_matrices.py",
    ]
    uncovered = [
        path for path in canonical_paths if not any(_github_path_matches(path, pattern) for pattern in workflow_paths)
    ]
    assert uncovered == [], f"CI scripts checker is not triggered by capability-matrix paths: {uncovered}"


def test_schema_enums_match_checker_constants() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for dimension, values in VALID_VALUES.items():
        assert dimension in schema["$defs"], f"schema lacks a $defs entry for {dimension}"
        assert set(schema["$defs"][dimension]["enum"]) == set(values), f"schema enum drifted for {dimension}"


def test_checker_rejects_more_included_actions_than_the_cap(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "microsoft")
    matrix["max_included_actions"] = 1
    for action in matrix["actions"][:2]:
        action["decision"] = "include"

    errors = validate_matrix(_save(root, "microsoft", matrix))

    assert any("exceeding max_included_actions=1" in error for error in errors)


def test_checker_rejects_cap_above_eight(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    matrix["max_included_actions"] = 9

    assert any("between 1 and 8" in error for error in validate_matrix(_save(root, "slack", matrix)))


def test_checker_rejects_unclassified_scope(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    matrix["actions"][0]["scopes"][0].pop("classification")

    assert any("is not classified" in error for error in validate_matrix(_save(root, "google", matrix)))


def test_checker_rejects_restricted_scope_without_decision(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    matrix["restricted_scope_decisions"] = []

    errors = validate_matrix(_save(root, "google", matrix))

    assert any("restricted scope" in error and "no restricted_scope_decisions entry" in error for error in errors)


def test_checker_rejects_include_on_avoided_restricted_scope(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    restricted = {
        scope["scope"]
        for action in matrix["actions"]
        for scope in action["scopes"]
        if scope.get("classification") == "restricted"
    }
    assert restricted, "fixture needs at least one restricted scope"
    target = next(action for action in matrix["actions"] if any(s["scope"] in restricted for s in action["scopes"]))
    target["decision"] = "include"
    for entry in matrix["restricted_scope_decisions"]:
        entry["decision"] = "avoid"

    errors = validate_matrix(_save(root, "google", matrix))

    assert any("contradiction" in error for error in errors)


def test_checker_rejects_unsourced_claim(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    matrix["actions"][0]["scopes"][0]["source"] = "does-not-exist"

    assert any("unknown source 'does-not-exist'" in error for error in validate_matrix(_save(root, "slack", matrix)))


def test_checker_rejects_future_verified_on(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    matrix["verified_on"] = "2999-01-01"

    assert any("is in the future" in error for error in validate_matrix(_save(root, "google", matrix)))


def test_checker_rejects_low_confidence_without_open_questions(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "microsoft")
    matrix["actions"][0]["confidence"] = "low"
    matrix["actions"][0]["open_questions"] = []

    assert any("must list open_questions" in error for error in validate_matrix(_save(root, "microsoft", matrix)))


def test_checker_rejects_high_confidence_on_non_ga_mcp(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    action = matrix["actions"][0]
    action.update({"substrate": "mcp", "substrate_ga_status": "developer_preview", "confidence": "high"})

    assert any("non-GA MCP substrate" in error for error in validate_matrix(_save(root, "google", matrix)))


def test_checker_reports_missing_matrix_file(tmp_path: Path) -> None:
    missing = tmp_path / "matrices" / "missing.json"

    assert validate_matrix(missing) == [
        f"could not read capability matrix {missing}: [Errno 2] No such file or directory: '{missing}'"
    ]


def test_checker_reports_malformed_matrix_json(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")

    errors = validate_matrix(malformed)

    assert len(errors) == 1
    assert "is not valid JSON" in errors[0]
    assert str(malformed) in errors[0]


def test_validate_all_reports_missing_provider(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    (root / "matrices" / "slack.json").unlink()

    assert any("missing capability matrices for ['slack']" in error for error in validate_all(root / "matrices"))


def test_require_accepted_fails_on_draft_record(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    record = root / "decisions" / "substrate-google.md"
    text = re.sub(r"^Status:.*$", "Status: draft", record.read_text(encoding="utf-8"), count=1, flags=re.MULTILINE)
    record.write_text(text, encoding="utf-8")

    assert validate_matrix(root / "matrices" / "google.json") == []
    errors = validate_matrix(root / "matrices" / "google.json", require_accepted=True)
    assert any("is draft, not accepted" in error for error in errors)
