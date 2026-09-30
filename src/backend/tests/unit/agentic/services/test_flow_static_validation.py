"""validate_flow_spec — Tier-1 static validation of a built flow.

Thin wrapper that reuses Langflow's existing CLI validator
(``validate_flow_file`` + the STRUCTURAL→REQUIRED_INPUTS semantic
checks) on an in-memory flow dict, with ZERO LLM tokens. Its own
responsibility is only: serialize → delegate → map to a small stable
report. Credentials are skipped (a missing user key is handled by the
agent-model resolver / honest caveat, NOT a fixable validation error).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from langflow.agentic.services.flow_static_validation import (
    FlowValidationReport,
    validate_flow_spec,
)

MODULE = "langflow.agentic.services.flow_static_validation"


def _fake_result(*, errors=(), warnings=()):
    from lfx.cli.validation.core import ValidationIssue, ValidationResult

    res = ValidationResult(path=Path("x"))
    for msg, node in errors:
        res.issues.append(ValidationIssue(level=2, severity="error", node_id=node, node_name=node, message=msg))
    for msg in warnings:
        res.issues.append(ValidationIssue(level=1, severity="warning", node_id=None, node_name=None, message=msg))
    return res


class TestValidateFlowSpecContract:
    def test_should_report_ok_when_the_validator_finds_no_errors(self):
        with patch(f"{MODULE}.validate_flow_file", return_value=_fake_result()):
            report = validate_flow_spec({"name": "f", "data": {"nodes": [], "edges": []}})

        assert isinstance(report, FlowValidationReport)
        assert report.ok is True
        assert report.errors == []

    def test_should_surface_errors_with_the_node_name_and_not_be_ok(self):
        with patch(
            f"{MODULE}.validate_flow_file",
            return_value=_fake_result(errors=[("Unknown component type 'FooBar'", "FooBar-1")]),
        ):
            report = validate_flow_spec({"name": "f", "data": {"nodes": [], "edges": []}})

        assert report.ok is False
        assert len(report.errors) == 1
        assert "FooBar" in report.errors[0]

    def test_should_separate_warnings_from_errors_and_stay_ok_on_warnings_only(self):
        with patch(
            f"{MODULE}.validate_flow_file",
            return_value=_fake_result(warnings=["Outdated component version"]),
        ):
            report = validate_flow_spec({"name": "f", "data": {"nodes": [], "edges": []}})

        assert report.ok is True
        assert report.errors == []
        assert any("Outdated" in w for w in report.warnings)

    def test_should_skip_credentials_so_a_missing_user_key_is_not_a_blocking_error(self):
        captured = {}

        def _spy(_path, **kwargs):
            captured.update(kwargs)
            return _fake_result()

        with patch(f"{MODULE}.validate_flow_file", side_effect=_spy):
            validate_flow_spec({"name": "f", "data": {"nodes": [], "edges": []}})

        assert captured.get("skip_credentials") is True

    def test_should_not_leave_a_temp_file_behind(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        seen = {}

        def _spy(path, **_kwargs):
            seen["path"] = Path(path)
            assert seen["path"].exists()  # file exists DURING validation
            return _fake_result()

        with patch(f"{MODULE}.validate_flow_file", side_effect=_spy):
            validate_flow_spec({"name": "f", "data": {"nodes": [], "edges": []}})

        # ...and is cleaned up afterwards.
        assert not seen["path"].exists()

    def test_should_be_resilient_when_the_flow_cannot_be_serialized(self):
        # A non-JSON-serializable value must NOT raise — return not-ok.
        report = validate_flow_spec({"data": {"nodes": [{"bad": {1, 2, 3}}]}})
        assert report.ok is False
        assert report.errors


class TestValidateFlowSpecRealReuse:
    def test_should_flag_an_unknown_component_type_via_the_real_validator(self):
        # No mock — proves the real lfx validator is actually wired.
        flow = {
            "id": "flow-1",  # _REQUIRED_TOP_LEVEL = {"id", "name", "data"}
            "name": "f",
            "data": {
                "nodes": [
                    {
                        "id": "Bogus-1",
                        "data": {
                            "type": "TotallyNotARealComponentType",
                            "id": "Bogus-1",
                            "node": {"template": {}},
                        },
                    }
                ],
                "edges": [],
            },
        }
        report = validate_flow_spec(flow)
        assert report.ok is False
        assert any("TotallyNotARealComponentType" in e for e in report.errors)
