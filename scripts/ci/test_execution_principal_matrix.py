from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_execution_principal_matrix import DEFAULT_MATRIX, REQUIRED_DIMENSIONS, validate_matrix

CI_SCRIPTS_WORKFLOW = DEFAULT_MATRIX.parents[2] / ".github" / "workflows" / "ci-scripts-test.yml"


def _workflow_pull_request_paths() -> list[str]:
    """Read the quoted pull-request path filters without adding a YAML dependency."""
    workflow = CI_SCRIPTS_WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count("    paths:\n") == 1, "expected exactly one pull-request paths block"
    assert "  workflow_dispatch:" in workflow, "expected workflow_dispatch to terminate the paths block"
    paths_block = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
    entries = [line.strip().removeprefix("- ") for line in paths_block.splitlines() if line.strip()]
    for entry in entries:
        assert entry.startswith('"'), f"path filter must start with a double quote: {entry}"
        assert entry.endswith('"'), f"path filter must end with a double quote: {entry}"
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
        elif pattern[index] == "?":
            regex_parts.append("[^/]")
            index += 1
        else:
            regex_parts.append(re.escape(pattern[index]))
            index += 1
    return re.fullmatch("".join(regex_parts), path) is not None


def test_execution_principal_matrix_is_complete() -> None:
    assert validate_matrix() == []


def test_every_entrypoint_declares_each_principal_and_safety_dimension() -> None:
    matrix = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))

    for entrypoint in matrix["entrypoints"]:
        assert set(entrypoint) >= REQUIRED_DIMENSIONS
        assert entrypoint["test_references"]


def test_ci_workflow_watches_every_canonical_source_and_test_reference() -> None:
    matrix = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    workflow_paths = _workflow_pull_request_paths()
    canonical_paths = {entrypoint["source"] for entrypoint in matrix["entrypoints"]} | {
        reference.split("::", 1)[0]
        for entrypoint in matrix["entrypoints"]
        for reference in entrypoint["test_references"]
    }

    uncovered = sorted(
        path for path in canonical_paths if not any(_github_path_matches(path, pattern) for pattern in workflow_paths)
    )
    assert uncovered == [], f"CI scripts checker is not triggered by canonical matrix paths: {uncovered}"


def test_checker_rejects_a_missing_error_policy(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    source["entrypoints"][0].pop("error_policy")
    incomplete = tmp_path / "execution-principal-matrix.json"
    incomplete.write_text(json.dumps(source), encoding="utf-8")

    assert any("error_policy" in error and "missing" in error for error in validate_matrix(incomplete))


def test_checker_reports_missing_matrix_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    assert validate_matrix(missing) == [
        f"could not read execution-principal matrix {missing}: [Errno 2] No such file or directory: '{missing}'"
    ]


def test_checker_reports_malformed_matrix_json(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")

    errors = validate_matrix(malformed)

    assert len(errors) == 1
    assert "is not valid JSON" in errors[0]
    assert str(malformed) in errors[0]


def test_checker_rejects_generic_non_behavioral_test_references(tmp_path: Path) -> None:
    source = json.loads(DEFAULT_MATRIX.read_text(encoding="utf-8"))
    generic_references = {
        "v1_run": "src/backend/tests/unit/api/v1/test_endpoints.py::test_get_config_basic",
        "webhook": "src/backend/tests/unit/api/v1/test_endpoints.py::test_get_version",
    }
    for entrypoint in source["entrypoints"]:
        if entrypoint["family"] in generic_references:
            entrypoint["test_references"] = [generic_references[entrypoint["family"]]]
    incomplete = tmp_path / "execution-principal-matrix.json"
    incomplete.write_text(json.dumps(source), encoding="utf-8")

    errors = validate_matrix(incomplete)
    assert any("v1_run" in error and "behavior-specific" in error for error in errors)
    assert any("webhook" in error and "behavior-specific" in error for error in errors)
