from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_capability_matrices import (
    DESIGN_ROOT,
    TRIGGERS_DESIGN_ROOT,
    is_event_transport_root,
    validate_all,
    validate_sign_offs,
)
from event_transport_matrix import MATRIX_SUFFIX, REQUIRED_PROVIDERS, SCHEMA_NAME, VALID_VALUES
from test_capability_matrices import _github_path_matches, _workflow_pull_request_paths

SCHEMA_PATH = TRIGGERS_DESIGN_ROOT / "schema" / SCHEMA_NAME
MATRIX_DIR = TRIGGERS_DESIGN_ROOT / "matrices"


def _copy_design(tmp_path: Path) -> Path:
    """Copy the whole triggers gate so a test can corrupt it without touching the repo."""
    root = tmp_path / "dedicated-integrations-triggers"
    shutil.copytree(TRIGGERS_DESIGN_ROOT, root)
    return root


def _load(root: Path, provider: str) -> dict:
    return json.loads((root / "matrices" / f"{provider}{MATRIX_SUFFIX}.json").read_text(encoding="utf-8"))


def _save(root: Path, provider: str, matrix: dict) -> Path:
    path = root / "matrices" / f"{provider}{MATRIX_SUFFIX}.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")
    return path


def _validate(root: Path) -> list[str]:
    return validate_all(root / "matrices", design_root=root)


def _mechanism(matrix: dict, mechanism_id: str) -> dict:
    return next(item for item in matrix["mechanisms"] if item["mechanism_id"] == mechanism_id)


def test_event_transport_matrices_are_complete() -> None:
    assert _validate(TRIGGERS_DESIGN_ROOT) == []


def test_sign_off_coverage_is_complete_for_the_triggers_gate() -> None:
    # Signatures are still outstanding, so only the coverage half (roles tracked, records listed) is asserted here.
    assert validate_sign_offs(TRIGGERS_DESIGN_ROOT) == []


def test_gate_close_mode_still_fails_because_signatures_are_outstanding() -> None:
    errors = validate_sign_offs(TRIGGERS_DESIGN_ROOT, require_complete=True)

    assert errors, "gate close cannot pass while the sign-off tables are empty"
    assert all("must complete Name, Date, and PR" in error for error in errors), errors


def test_every_required_provider_has_an_events_matrix() -> None:
    present = {path.stem.removesuffix(MATRIX_SUFFIX) for path in MATRIX_DIR.glob(f"*{MATRIX_SUFFIX}.json")}

    assert present == set(REQUIRED_PROVIDERS)


def test_design_root_flag_selects_the_gate_profile() -> None:
    assert is_event_transport_root(TRIGGERS_DESIGN_ROOT)
    assert not is_event_transport_root(DESIGN_ROOT), "the INT-1 gate must keep the capability-matrix rules"


def test_capability_gate_is_unchanged_without_the_flag() -> None:
    assert validate_all() == []


def test_schema_enums_match_checker_constants() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for dimension, values in VALID_VALUES.items():
        assert dimension in schema["$defs"], f"schema lacks a $defs entry for {dimension}"
        assert set(schema["$defs"][dimension]["enum"]) == set(values), f"schema enum drifted for {dimension}"


def test_ci_workflow_watches_the_triggers_gate() -> None:
    workflow_paths = _workflow_pull_request_paths()
    canonical_paths = [
        "design/dedicated-integrations-triggers/matrices/slack-events.json",
        "design/dedicated-integrations-triggers/decisions/process-model.md",
        "scripts/ci/event_transport_matrix.py",
    ]
    uncovered = [
        path for path in canonical_paths if not any(_github_path_matches(path, pattern) for pattern in workflow_paths)
    ]

    assert uncovered == [], f"CI scripts checker is not triggered by triggers-gate paths: {uncovered}"


def test_push_mechanism_cannot_claim_a_context_without_ingress(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    _mechanism(matrix, "slack.events_api")["deployment_contexts"].append("desktop")
    _save(root, "slack", matrix)

    errors = _validate(root)

    assert any("claims context 'desktop'" in error and "ingress is unavailable" in error for error in errors), errors


def test_push_mechanism_in_a_conditional_context_needs_a_fallback(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "microsoft")
    _mechanism(matrix, "microsoft.graph_change_notifications").pop("fallback_mechanism")
    _save(root, "microsoft", matrix)

    errors = _validate(root)

    assert any("without naming a fallback_mechanism" in error for error in errors), errors


def test_fallback_must_be_outbound_only(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "microsoft")
    _mechanism(matrix, "microsoft.graph_delta_poll")["ingress_requirement"] = "public_https"
    _save(root, "microsoft", matrix)

    errors = _validate(root)

    assert any("is not outbound-only" in error for error in errors), errors


def test_fallback_must_support_the_same_context(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    _mechanism(matrix, "google.calendar_sync_poll")["deployment_contexts"] = ["desktop"]
    _save(root, "google", matrix)

    errors = _validate(root)

    assert any("does not support context 'self_managed'" in error for error in errors), errors


def test_unknown_fallback_mechanism_is_rejected(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    _mechanism(matrix, "slack.events_api")["fallback_mechanism"] = "slack.nonexistent"
    _save(root, "slack", matrix)

    errors = _validate(root)

    assert any("names unknown fallback_mechanism 'slack.nonexistent'" in error for error in errors), errors


def test_provider_without_an_outbound_only_mechanism_is_rejected(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    socket_mode = _mechanism(matrix, "slack.socket_mode")
    socket_mode["status"] = "deferred"
    socket_mode["deployment_contexts"] = []
    _save(root, "slack", matrix)

    errors = _validate(root)

    assert any("no wave-1 mechanism runs outbound-only" in error for error in errors), errors


def test_unknown_source_reference_is_rejected(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    _mechanism(matrix, "google.gmail_watch_pubsub_pull")["replay"]["source"] = "no-such-source"
    _save(root, "google", matrix)

    errors = _validate(root)

    assert any("references unknown source 'no-such-source'" in error for error in errors), errors


def test_wave_1_mechanism_must_carry_every_claim_block(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "microsoft")
    _mechanism(matrix, "microsoft.graph_delta_poll").pop("rate_limit")
    _save(root, "microsoft", matrix)

    errors = _validate(root)

    assert any("is a wave-1 mechanism and is missing ['rate_limit']" in error for error in errors), errors


def test_excluded_mechanism_may_not_claim_a_context(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "microsoft")
    _mechanism(matrix, "microsoft.teams_message_notifications")["deployment_contexts"] = ["hosted"]
    _save(root, "microsoft", matrix)

    errors = _validate(root)

    assert any("is excluded and must not claim deployment contexts" in error for error in errors), errors


def test_low_confidence_mechanism_must_list_open_questions(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "google")
    mechanism = _mechanism(matrix, "google.drive_changes_poll")
    mechanism["confidence"] = "low"
    _save(root, "google", matrix)

    errors = _validate(root)

    assert any("is low confidence and must list open_questions" in error for error in errors), errors


def test_future_verified_on_is_rejected(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    matrix["verified_on"] = "2099-01-01"
    _save(root, "slack", matrix)

    errors = _validate(root)

    assert any("verified_on '2099-01-01' is in the future" in error for error in errors), errors


def test_matrix_file_name_must_match_the_provider(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    matrix["provider"] = "google"
    _save(root, "slack", matrix)

    errors = _validate(root)

    assert any("does not match file name 'slack-events'" in error for error in errors), errors


def test_stray_matrix_file_name_is_rejected(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    (root / "matrices" / "slack.json").write_text("{}", encoding="utf-8")

    errors = _validate(root)

    assert any("matrices must be named '<provider>-events.json'" in error for error in errors), errors


def test_missing_decision_record_is_rejected(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    (root / "decisions" / "process-model.md").unlink()

    errors = _validate(root)

    assert any("decision record 'decisions/process-model.md' does not exist" in error for error in errors), errors


def test_require_accepted_rejects_a_draft_decision_record(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    record = root / "decisions" / "delivery-semantics.md"
    record.write_text(record.read_text(encoding="utf-8").replace("Status: accepted", "Status: draft", 1), "utf-8")

    errors = _validate(root)
    accepted_errors = validate_all(root / "matrices", design_root=root, require_accepted=True)

    assert errors == [], "a draft record is fine outside gate-close mode"
    assert any("is draft, not accepted" in error for error in accepted_errors), accepted_errors


def test_a_malformed_claim_block_is_reported_not_raised(tmp_path: Path) -> None:
    # A gate checker must fail the gate, never fail itself: a scalar where an object belongs
    # is a schema violation and must come back as an error string.
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    _mechanism(matrix, "slack.events_api")["inbound_auth"] = "signature"
    _save(root, "slack", matrix)

    errors = _validate(root)

    assert any("inbound_auth must be an object" in error for error in errors), errors
    assert sum("inbound_auth must be an object" in error for error in errors) == 1, errors


def test_an_unhashable_mechanism_id_is_reported_not_raised(tmp_path: Path) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    _mechanism(matrix, "slack.socket_mode")["mechanism_id"] = ["slack", "socket_mode"]
    _save(root, "slack", matrix)

    errors = _validate(root)

    assert any("mechanism_id must look like" in error for error in errors), errors
