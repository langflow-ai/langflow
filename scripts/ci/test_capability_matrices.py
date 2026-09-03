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
    validate_decision_records,
    validate_matrix,
    validate_sign_offs,
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


def _copy_design_tree(tmp_path: Path) -> Path:
    """Copy the whole design directory (README, records, matrices) for sign-off coverage tests."""
    root = tmp_path / "dedicated-integrations"
    shutil.copytree(DESIGN_ROOT, root)
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
    # The rule applies to included and deferred rows; an excluded row may carry an undecided restricted scope.
    for action in matrix["actions"]:
        if any(scope.get("classification") == "restricted" for scope in action["scopes"]):
            action["decision"] = "defer"
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


def _included_action(matrix: dict) -> dict:
    return next(action for action in matrix["actions"] if action["decision"] == "include")


def test_every_included_scope_carries_a_role() -> None:
    for provider in REQUIRED_PROVIDERS:
        matrix = _load(DESIGN_ROOT, provider)
        for action in matrix["actions"]:
            if action["decision"] != "include":
                continue
            roles = [scope.get("role") for scope in action["scopes"]]
            assert None not in roles, f"{action['action_id']} has an untagged scope"
            assert "required" in roles, f"{action['action_id']} has no required scope"


def test_checker_rejects_included_scope_without_role(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "microsoft")
    _included_action(matrix)["scopes"][0].pop("role")

    errors = validate_matrix(_save(root, "microsoft", matrix))

    assert any("must declare a role" in error for error in errors)


def test_checker_rejects_included_action_without_required_scope(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    action = _included_action(matrix)
    input_name = action["schema"]["inputs"][0]["name"]
    for scope in action["scopes"]:
        scope.update({"role": "optional", "condition": {"kind": "input_present", "input": input_name}})

    errors = validate_matrix(_save(root, "google", matrix))

    assert any("declares no required scope" in error for error in errors)


def test_checker_rejects_conditional_scope_without_condition(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    scope = _included_action(matrix)["scopes"][0]
    scope["role"] = "alternative"
    scope.pop("condition", None)

    errors = validate_matrix(_save(root, "slack", matrix))

    assert any("must state the condition" in error for error in errors)


def test_checker_rejects_required_scope_with_condition(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    action = _included_action(matrix)
    action["scopes"][0]["condition"] = {
        "kind": "input_present",
        "input": action["schema"]["inputs"][0]["name"],
    }

    errors = validate_matrix(_save(root, "google", matrix))

    assert any("must not carry a condition" in error for error in errors)


def test_schema_rejects_prose_scope_condition(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "microsoft")
    action = next(action for action in matrix["actions"] if action["action_id"] == "microsoft.files.list")
    conditional_scope = next(scope for scope in action["scopes"] if scope["role"] == "optional")
    conditional_scope["condition"] = "drive_id is set"

    errors = validate_matrix(_save(root, "microsoft", matrix))

    assert any("is not of type 'object'" in error for error in errors)


def test_checker_rejects_scope_condition_for_unknown_input(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "microsoft")
    action = next(action for action in matrix["actions"] if action["action_id"] == "microsoft.files.list")
    conditional_scope = next(scope for scope in action["scopes"] if scope["role"] == "optional")
    conditional_scope["condition"]["input"] = "missing_input"

    errors = validate_matrix(_save(root, "microsoft", matrix))

    assert any("condition references unknown action input 'missing_input'" in error for error in errors)


def test_schema_validation_rejects_empty_outputs(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    _included_action(matrix)["schema"]["outputs"] = []

    errors = validate_matrix(_save(root, "google", matrix))

    assert any(
        error.startswith("schema: actions/") and error.endswith("/schema/outputs: [] should be non-empty")
        for error in errors
    )


def test_schema_validation_rejects_unknown_action_field(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    matrix["actions"][0]["scope_notes"] = "typo for notes"

    errors = validate_matrix(_save(root, "slack", matrix))

    assert any(error.startswith("schema: actions/0:") and "'scope_notes' was unexpected" in error for error in errors)


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


def test_every_declared_owner_is_tracked_in_sign_off_tables() -> None:
    assert validate_sign_offs() == []


def test_gate_close_rejects_blank_owner_signatures() -> None:
    errors = validate_sign_offs(require_complete=True)

    assert "sign-off: README.md row 'lfx owner' must complete Name, Date, and PR" in errors
    assert any(
        "decisions/substrate-google.md row 'lfx owner' must complete Name, Date, and PR" in error for error in errors
    )


def test_gate_close_accepts_completed_owner_signatures(tmp_path: Path) -> None:
    root = _copy_design_tree(tmp_path)
    for record in root.rglob("*.md"):
        text = record.read_text(encoding="utf-8")
        record.write_text(
            text.replace("| | | |", "| Test Owner | 2026-09-01 | #14906 |"),
            encoding="utf-8",
        )

    assert validate_sign_offs(root, require_complete=True) == []


def test_sign_off_check_rejects_owner_missing_from_readme_and_record_tables(tmp_path: Path) -> None:
    root = _copy_design_tree(tmp_path)
    record = root / "decisions" / "substrate-google.md"
    text = record.read_text(encoding="utf-8").replace(
        "Owners (sign-off roles): lfx owner,", "Owners (sign-off roles): platform owner, lfx owner,", 1
    )
    record.write_text(text, encoding="utf-8")

    errors = validate_sign_offs(root)

    assert "sign-off: README.md row for 'platform owner' does not list `decisions/substrate-google.md`" in errors
    assert "sign-off: decisions/substrate-google.md table lacks a row for 'platform owner'" in errors


def test_sign_off_check_rejects_record_dropped_from_readme_row(tmp_path: Path) -> None:
    root = _copy_design_tree(tmp_path)
    readme = root / "README.md"
    # The record is also cited in the exit-criteria table above the sign-off section; only the sign-off rows change.
    head, sign_off = readme.read_text(encoding="utf-8").split("## Sign-off", 1)
    sign_off = sign_off.replace("`decisions/kb-oauth-connector-adoption.md`", "")
    readme.write_text(head + "## Sign-off" + sign_off, encoding="utf-8")

    errors = validate_sign_offs(root)

    assert "sign-off: README.md row for 'lfx owner' does not list `decisions/kb-oauth-connector-adoption.md`" in errors
    assert (
        "sign-off: README.md row for 'langflow-base owner' does not list `decisions/kb-oauth-connector-adoption.md`"
        in errors
    )


def test_sign_off_check_rejects_undeclared_row_in_record_table(tmp_path: Path) -> None:
    root = _copy_design_tree(tmp_path)
    record = root / "decisions" / "palette-naming.md"
    text = record.read_text(encoding="utf-8").replace(
        "| product owner | | | |", "| product owner | | | |\n| lfx owner | | | |", 1
    )
    record.write_text(text, encoding="utf-8")

    errors = validate_sign_offs(root)

    assert "sign-off: decisions/palette-naming.md table row 'lfx owner' is not a declared owner" in errors


def test_sign_off_check_rejects_record_without_sign_off_table(tmp_path: Path) -> None:
    root = _copy_design_tree(tmp_path)
    record = root / "frontend-surfaces.md"
    record.write_text(record.read_text(encoding="utf-8").split("## Sign-off", 1)[0], encoding="utf-8")

    errors = validate_sign_offs(root)

    assert (
        "sign-off: frontend-surfaces.md declares ['frontend owner', 'release owner'] but has no '## Sign-off' table"
        in errors
    )


def test_sign_off_check_reports_deleted_readme(tmp_path: Path) -> None:
    root = _copy_design_tree(tmp_path)
    (root / "README.md").unlink()

    assert validate_sign_offs(root) == [f"sign-off: {root / 'README.md'} does not exist"]


def test_require_accepted_walks_every_decision_record(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    # palette-naming.md is not referenced from any matrix; gate close must still require it to be accepted.
    record = root / "decisions" / "palette-naming.md"
    text = re.sub(r"^Status:.*$", "Status: draft", record.read_text(encoding="utf-8"), count=1, flags=re.MULTILINE)
    record.write_text(text, encoding="utf-8")

    assert validate_decision_records(root) == []
    assert validate_all(root / "matrices") == []
    errors = validate_all(root / "matrices", require_accepted=True)
    assert "gate decision record 'decisions/palette-naming.md' is draft, not accepted" in errors


def test_require_accepted_fails_on_draft_record(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    record = root / "decisions" / "substrate-google.md"
    text = re.sub(r"^Status:.*$", "Status: draft", record.read_text(encoding="utf-8"), count=1, flags=re.MULTILINE)
    record.write_text(text, encoding="utf-8")

    assert validate_matrix(root / "matrices" / "google.json") == []
    errors = validate_matrix(root / "matrices" / "google.json", require_accepted=True)
    assert any("is draft, not accepted" in error for error in errors)


def test_desktop_uses_langflow_owned_public_clients() -> None:
    """decisions/desktop-oauth-ownership.md: Desktop defaults to a Langflow-owned PKCE public client."""
    for provider in REQUIRED_PROVIDERS:
        matrix = _load(DESIGN_ROOT, provider)
        assert matrix["oauth_app_owner_by_context"]["desktop"] == "langflow", provider
        assert matrix["oauth_client_type_by_context"]["desktop"] == "public", provider
        for action in matrix["actions"]:
            if action["decision"] != "include":
                continue
            contexts = action["deployment_contexts"]
            if action["identity"] == "bot":
                assert "desktop" not in contexts, f"{action['action_id']} offers bot scopes on Desktop"
            else:
                assert contexts.get("desktop") == "loopback_redirect", action["action_id"]
