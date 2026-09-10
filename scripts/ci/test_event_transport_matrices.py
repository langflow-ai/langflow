from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from check_capability_matrices import (
    DESIGN_ROOT,
    TRIGGERS_DESIGN_ROOT,
    is_event_transport_root,
    main,
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


def _complete_signatures(root: Path) -> None:
    """Synthetic signatures for negative tests; never modify the real gate."""
    for record in root.rglob("*.md"):
        text = record.read_text(encoding="utf-8")
        text = text.replace("| | | |", "| Test reviewer | 2026-09-05 | #1 |")
        record.write_text(text, encoding="utf-8")


def _complete_gate(root: Path) -> None:
    _complete_signatures(root)
    findings = root / "findings" / "2026-09-listeners.md"
    findings.write_text(
        findings.read_text(encoding="utf-8")
        .replace("Status: draft", "Status: accepted")
        .replace("To be written by the platform owner.", "Reviewed in this synthetic test fixture."),
        encoding="utf-8",
    )
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    before, section = text.split("## Exit criteria and where each one lives", 1)
    section, after = section.split("\n## ", 1)
    section = re.sub(r"^(\| [1-9] \|.*\|)[^|]+\|$", r"\1 done 2026-09-05 |", section, flags=re.MULTILINE)
    readme.write_text(before + "## Exit criteria and where each one lives" + section + "\n## " + after, "utf-8")


def test_gate_close_rejects_signed_findings_stub(tmp_path: Path, monkeypatch, capsys) -> None:
    root = _copy_design(tmp_path)
    _complete_signatures(root)
    (root / "findings" / "2026-09-listeners.md").write_text(
        "# Findings\n\nStatus: draft\nOwners (sign-off roles): platform owner, release owner\n\n"
        "TODO: write this document\n\n## Sign-off\n\n| Role | Name | Date | PR |\n|---|---|---|---|\n"
        "| platform owner | Test reviewer | 2026-09-05 | #1 |\n"
        "| release owner | Test reviewer | 2026-09-05 | #1 |\n",
        encoding="utf-8",
    )
    assert validate_sign_offs(root, require_complete=True) == []
    monkeypatch.setattr(sys, "argv", ["checker", "--design-root", str(root), "--require-accepted"])

    assert main() == 1
    output = capsys.readouterr().out
    assert "findings/2026-09-listeners.md" in output
    assert "exit criterion 1" in output
    assert "exit criterion 7" in output


def test_completed_gate_passes_cli(tmp_path: Path, monkeypatch, capsys) -> None:
    root = _copy_design(tmp_path)
    _complete_gate(root)
    monkeypatch.setattr(sys, "argv", ["checker", "--design-root", str(root), "--require-accepted"])

    assert main() == 0
    assert "matrices are complete" in capsys.readouterr().out


@pytest.mark.parametrize("status", ["draft", "proposed", "superseded", "missing"])
def test_gate_close_requires_accepted_findings(tmp_path: Path, status: str) -> None:
    root = _copy_design(tmp_path)
    _complete_gate(root)
    record = root / "findings" / "2026-09-listeners.md"
    record.write_text(record.read_text().replace("Status: accepted", f"Status: {status}"), "utf-8")

    errors = validate_all(root / "matrices", design_root=root, require_accepted=True)

    assert any("findings/2026-09-listeners.md" in error and "accepted" in error for error in errors), errors


@pytest.mark.parametrize(
    "record", ["findings/2026-09-listeners.md", "trigger-contract.md", "frontend-surfaces.md", "estimate.md"]
)
def test_gate_close_requires_each_gate_artifact(tmp_path: Path, record: str) -> None:
    root = _copy_design(tmp_path)
    _complete_gate(root)
    (root / record).unlink()

    errors = validate_all(root / "matrices", design_root=root, require_accepted=True)

    assert any(record in error and "does not exist" in error for error in errors), errors


@pytest.mark.parametrize("criterion", range(1, 10))
def test_gate_close_requires_every_exit_criterion_done(tmp_path: Path, criterion: int) -> None:
    root = _copy_design(tmp_path)
    _complete_gate(root)
    readme = root / "README.md"
    text = re.sub(
        rf"^(\| {criterion} \|.*\|) done 2026-09-05 \|$",
        r"\1 **open**: needs review |",
        readme.read_text(),
        flags=re.MULTILINE,
    )
    readme.write_text(text, "utf-8")

    errors = validate_all(root / "matrices", design_root=root, require_accepted=True)

    assert any(f"exit criterion {criterion} " in error for error in errors), errors


@pytest.mark.parametrize("change", ["missing", "duplicate", "bad_date", "future_date", "ambiguous_status"])
def test_gate_close_rejects_invalid_conformance_row(tmp_path: Path, change: str) -> None:
    root = _copy_design(tmp_path)
    _complete_gate(root)
    readme = root / "README.md"
    text = readme.read_text()
    row = next(line for line in text.splitlines() if line.startswith("| 7 | 1.13 conformance"))
    replacement = {
        "missing": "",
        "duplicate": row + "\n" + row,
        "bad_date": row.replace("2026-09-05", "2026-02-30"),
        "future_date": row.replace("2026-09-05", "2099-01-01"),
        "ambiguous_status": row.replace("done 2026-09-05", "done 2026-09-05; conformance still open"),
    }[change]
    readme.write_text(text.replace(row, replacement), "utf-8")

    errors = validate_all(root / "matrices", design_root=root, require_accepted=True)

    assert any("exit criteri" in error for error in errors), errors


@pytest.mark.parametrize("body", ["TODO: write this document", "To be written by the platform owner."])
def test_gate_close_rejects_accepted_findings_placeholder(tmp_path: Path, body: str) -> None:
    root = _copy_design(tmp_path)
    _complete_gate(root)
    record = root / "findings" / "2026-09-listeners.md"
    record.write_text(record.read_text() + "\n" + body, "utf-8")

    errors = validate_all(root / "matrices", design_root=root, require_accepted=True)

    assert any("findings/2026-09-listeners.md" in error and "unfinished" in error for error in errors), errors


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


@pytest.mark.parametrize("bad_value", [[], {}], ids=["list", "object"])
@pytest.mark.parametrize(
    ("field_path", "dimension"),
    [
        (("provider",), "provider"),
        (("sources", "slack-events-api", "kind"), "source_kind"),
        (("public_ingress_by_context", "hosted"), "ingress_availability"),
        (("mechanisms", 0, "track"), "track"),
        (("mechanisms", 0, "transport"), "transport"),
        (("mechanisms", 0, "ingress_requirement"), "ingress_requirement"),
        (("mechanisms", 0, "confidence"), "confidence"),
        (("mechanisms", 0, "status"), "mechanism_status"),
        (("mechanisms", 0, "inbound_auth", "method"), "inbound_auth_method"),
        (("mechanisms", 0, "payload", "shape"), "payload_shape"),
        (("mechanisms", 0, "delivery", "guarantee"), "delivery_guarantee"),
        (("mechanisms", 0, "dedupe_key", "stability"), "dedupe_stability"),
    ],
)
def test_malformed_enum_is_reported_not_raised(tmp_path: Path, field_path: tuple, dimension: str, bad_value) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    parent = matrix
    for key in field_path[:-1]:
        parent = parent[key]
    parent[field_path[-1]] = bad_value
    _save(root, "slack", matrix)

    errors = _validate(root)

    assert any(f"unknown {dimension}" in error for error in errors), errors


@pytest.mark.parametrize("contexts", [[[]], [{}], {"self_managed": True}, 1])
@pytest.mark.parametrize("mechanism_id", ["slack.events_api", "slack.socket_mode"])
def test_malformed_deployment_contexts_are_reported_not_raised(tmp_path: Path, mechanism_id: str, contexts) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    _mechanism(matrix, mechanism_id)["deployment_contexts"] = contexts
    _save(root, "slack", matrix)

    errors = _validate(root)

    assert any("deployment_contexts must be a list" in error for error in errors), errors
    if mechanism_id == "slack.socket_mode":
        assert any("does not support context 'self_managed'" in error for error in errors), errors


@pytest.mark.parametrize("fallback_id", [[], {}, ["slack.socket_mode"], {"id": "slack.socket_mode"}])
def test_malformed_fallback_identifier_fails_cli(tmp_path: Path, monkeypatch, capsys, fallback_id) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, "slack")
    _mechanism(matrix, "slack.events_api")["fallback_mechanism"] = fallback_id
    _save(root, "slack", matrix)
    monkeypatch.setattr(sys, "argv", ["checker", "--design-root", str(root)])

    assert main() == 1
    assert "names unknown fallback_mechanism" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("provider", "mechanism_id"),
    [
        ("slack", "slack.rtm_api"),
        ("microsoft", "microsoft.graph_notifications_with_resource_data"),
        ("microsoft", "microsoft.teams_message_notifications"),
    ],
)
def test_exclusion_basis_source_must_resolve(tmp_path: Path, provider: str, mechanism_id: str) -> None:
    root = _copy_design(tmp_path)
    matrix = _load(root, provider)
    _mechanism(matrix, mechanism_id)["exclusion_basis"] = {"details": "Out of scope", "source": "no-such-source"}
    _save(root, provider, matrix)

    errors = _validate(root)

    assert any("exclusion_basis references unknown source 'no-such-source'" in error for error in errors), errors
