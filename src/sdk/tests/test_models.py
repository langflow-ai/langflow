"""Unit tests for SDK models and environment config."""
# pragma: allowlist secret -- this file only contains fake test credentials

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from uuid import UUID

import pytest
from langflow_sdk.models import Flow, FlowCreate, FlowUpdate, Project, RunOutput, RunRequest, RunResponse

# ---------------------------------------------------------------------------
# Model round-trip tests
# ---------------------------------------------------------------------------


def test_flow_parse_minimal():
    data = {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "My Flow",
    }
    flow = Flow.model_validate(data)
    assert flow.id == UUID("00000000-0000-0000-0000-000000000001")
    assert flow.name == "My Flow"
    assert flow.is_component is False


def test_flow_create_exclude_none():
    fc = FlowCreate(name="Test")
    dumped = fc.model_dump(exclude_none=True)
    assert "description" not in dumped
    assert dumped["name"] == "Test"


def test_flow_update_partial():
    fu = FlowUpdate(name="Renamed")
    dumped = fu.model_dump(exclude_none=True)
    assert dumped == {"name": "Renamed"}


def test_project_parse():
    data = {
        "id": "00000000-0000-0000-0000-000000000002",
        "name": "My Project",
        "parent_id": None,
    }
    p = Project.model_validate(data)
    assert p.name == "My Project"


def test_run_request_defaults():
    req = RunRequest()
    assert req.input_type == "chat"
    assert req.output_type == "chat"
    assert req.stream is False


def test_run_response_empty():
    resp = RunResponse.model_validate({"outputs": []})
    assert resp.outputs == []


# ---------------------------------------------------------------------------
# RunOutput.has_errors
# ---------------------------------------------------------------------------

_COMPONENT_OUT_TEXT = {
    "results": {"message": {"text": "Hello"}},
    "artifacts": {},
    "outputs": [{"results": {"message": {"text": "Hello"}}}],
}

_COMPONENT_OUT_ERROR = {
    "results": {},
    "artifacts": {},
    "outputs": [{"error": "Something went wrong"}],
}

_COMPONENT_OUT_ARTIFACT_ERROR = {
    "results": {},
    "artifacts": {"error": "artifact error"},
    "outputs": [],
}


def test_run_output_has_errors_false_when_clean():
    out = RunOutput.model_validate(_COMPONENT_OUT_TEXT)
    assert out.has_errors() is False


def test_run_output_has_errors_true_when_component_error():
    out = RunOutput(
        results={},
        artifacts={},
        outputs=[{"error": "Something went wrong"}],
    )
    assert out.has_errors() is True


def test_run_output_has_errors_true_when_artifact_error():
    out = RunOutput(results={}, artifacts={"error": "artifact error"}, outputs=[])
    assert out.has_errors() is True


def test_run_output_has_errors_false_empty_outputs():
    out = RunOutput(results={}, artifacts={}, outputs=[])
    assert out.has_errors() is False


# ---------------------------------------------------------------------------
# RunResponse WorkflowResponse-style helpers
# ---------------------------------------------------------------------------

_OUTPUT_WITH_TEXT = {
    "results": {},
    "artifacts": {},
    "outputs": [{"results": {"message": {"text": "Hi there"}}}],
}

_OUTPUT_WITH_ERROR = {
    "results": {},
    "artifacts": {},
    "outputs": [{"error": "boom"}],
}


def _make_response(*output_dicts: dict) -> RunResponse:
    return RunResponse.model_validate({"outputs": list(output_dicts)})


class TestRunResponseHelpers:
    def test_get_chat_output_returns_first_text(self):
        resp = _make_response(_OUTPUT_WITH_TEXT)
        assert resp.get_chat_output() == "Hi there"

    def test_get_chat_output_none_when_empty(self):
        resp = RunResponse()
        assert resp.get_chat_output() is None

    def test_get_all_outputs_returns_list_of_run_outputs(self):
        resp = _make_response(_OUTPUT_WITH_TEXT, _OUTPUT_WITH_TEXT)
        result = resp.get_all_outputs()
        assert len(result) == len(resp.outputs)
        assert all(isinstance(o, RunOutput) for o in result)

    def test_get_all_outputs_empty(self):
        assert _make_response().get_all_outputs() == []

    def test_get_text_outputs_returns_strings(self):
        resp = _make_response(_OUTPUT_WITH_TEXT, _OUTPUT_WITH_TEXT)
        assert resp.get_text_outputs() == ["Hi there", "Hi there"]

    def test_get_text_outputs_empty(self):
        assert RunResponse().get_text_outputs() == []

    def test_has_errors_false_when_clean(self):
        resp = _make_response(_OUTPUT_WITH_TEXT)
        assert resp.has_errors() is False

    def test_has_errors_true_when_output_errors(self):
        resp = _make_response(_OUTPUT_WITH_ERROR)
        assert resp.has_errors() is True

    def test_has_errors_false_empty_response(self):
        assert RunResponse().has_errors() is False

    def test_has_errors_mixed_clean_and_error(self):
        resp = _make_response(_OUTPUT_WITH_TEXT, _OUTPUT_WITH_ERROR)
        assert resp.has_errors() is True

    def test_is_completed_true_with_outputs_no_errors(self):
        resp = _make_response(_OUTPUT_WITH_TEXT)
        assert resp.is_completed() is True

    def test_is_completed_false_when_empty(self):
        assert RunResponse().is_completed() is False

    def test_is_completed_false_when_errors(self):
        resp = _make_response(_OUTPUT_WITH_ERROR)
        assert resp.is_completed() is False

    def test_is_failed_false_with_clean_outputs(self):
        resp = _make_response(_OUTPUT_WITH_TEXT)
        assert resp.is_failed() is False

    def test_is_failed_true_when_no_outputs(self):
        assert RunResponse().is_failed() is True

    def test_is_failed_true_when_errors(self):
        resp = _make_response(_OUTPUT_WITH_ERROR)
        assert resp.is_failed() is True

    def test_is_in_progress_always_false(self):
        assert RunResponse().is_in_progress() is False
        assert _make_response(_OUTPUT_WITH_TEXT).is_in_progress() is False

    def test_status_helpers_consistent(self):
        """is_completed and is_failed are mutually exclusive for non-empty responses."""
        resp = _make_response(_OUTPUT_WITH_TEXT)
        assert resp.is_completed() != resp.is_failed()

    def test_get_chat_output_alias_matches_first_text_output(self):
        resp = _make_response(_OUTPUT_WITH_TEXT)
        assert resp.get_chat_output() == resp.first_text_output()


# ---------------------------------------------------------------------------
# Environment config tests
# ---------------------------------------------------------------------------


def test_load_environments(tmp_path: Path):
    config = tmp_path / "langflow-environments.toml"
    config.write_text(
        textwrap.dedent("""\
            [environments.staging]
            url = "https://staging.example.com"
            api_key_env = "TEST_KEY_STAGING" # pragma: allowlist secret

            [environments.production]
            url = "https://prod.example.com"
            api_key = "not-a-real-secret"  # pragma: allowlist secret

            [defaults]
            environment = "staging"
        """),
        encoding="utf-8",
    )
    fake_key = "test-key-not-a-real-secret"  # pragma: allowlist secret
    os.environ["TEST_KEY_STAGING"] = fake_key

    from langflow_sdk.environments import get_environment, load_environments

    try:
        envs = load_environments(config)
        assert "staging" in envs
        assert envs["staging"].url == "https://staging.example.com"
        assert envs["staging"].api_key == fake_key
        assert envs["production"].api_key == "not-a-real-secret"  # pragma: allowlist secret

        default_env = get_environment(config_file=config)
        assert default_env.name == "staging"
    finally:
        os.environ.pop("TEST_KEY_STAGING", None)


def test_environment_not_found(tmp_path: Path):
    config = tmp_path / "langflow-environments.toml"
    config.write_text("[environments.staging]\nurl = 'https://x.com'\n")

    from langflow_sdk.environments import get_environment
    from langflow_sdk.exceptions import EnvironmentNotFoundError

    with pytest.raises(EnvironmentNotFoundError, match="production"):
        get_environment("production", config_file=config)


def test_missing_url_raises(tmp_path: Path):
    config = tmp_path / "langflow-environments.toml"
    # Intentionally omit 'url' to trigger the validation error
    config.write_text("[environments.bad]\ndescription = 'oops'\n")

    from langflow_sdk.environments import load_environments
    from langflow_sdk.exceptions import EnvironmentConfigError

    with pytest.raises(EnvironmentConfigError, match="url"):
        load_environments(config)
