"""Security gates on the agentic assistant's in-process code-execution path (Issue 15).

The assistant generates component code and EXECUTES it in-process (validate_component_runtime ->
build_custom_component_template -> compile/exec; and again in the user-components overlay). These
tests assert the two hardening gates:
  (a) the agentic endpoints are unreachable (404) unless agentic_experience is enabled;
  (b) the execution entry points refuse when allow_custom_components is disabled.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _settings(*, allow_custom=True, agentic=True, admin_only=False):
    s = MagicMock()
    s.settings.allow_custom_components = allow_custom
    s.settings.agentic_experience = agentic
    s.settings.custom_component_admin_only = admin_only
    s.settings.assistant_max_message_length = 1000
    return s


# --- (a) endpoint gate: require_agentic_experience ---------------------------------------------


def test_require_agentic_experience_404_when_disabled():
    from fastapi import HTTPException
    from langflow.agentic.api.deps import require_agentic_experience

    with patch("langflow.agentic.api.deps.get_settings_service", return_value=_settings(agentic=False)):
        with pytest.raises(HTTPException) as exc:
            require_agentic_experience()
        assert exc.value.status_code == 404


def test_require_agentic_experience_allows_when_enabled():
    from langflow.agentic.api.deps import require_agentic_experience

    with patch("langflow.agentic.api.deps.get_settings_service", return_value=_settings(agentic=True)):
        assert require_agentic_experience() is None


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/agentic/execute/assistant", {"flow_id": ""}),
        ("/agentic/assist", {"flow_id": ""}),
        ("/agentic/assist/stream", {"flow_id": ""}),
        ("/agentic/assist/run", {"instruction": "build a component"}),
    ],
)
def test_assistant_execution_denies_non_admin_when_custom_code_is_admin_only(path: str, body: dict):
    """Every HTTP entry point refuses before loading a provider or executing code."""
    from types import SimpleNamespace
    from uuid import uuid4

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from langflow.agentic.api.router import router
    from langflow.services.auth.utils import get_current_active_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=uuid4(), is_superuser=False)
    settings = _settings(admin_only=True)
    with (
        patch("langflow.agentic.api.deps.get_settings_service", return_value=settings),
        patch("langflow.agentic.api.router.get_settings_service", return_value=settings),
        patch("lfx.services.deps.get_settings_service", return_value=settings),
    ):
        response = TestClient(app).post(path, json=body)

    assert response.status_code == 403
    assert response.json()["detail"] == "The Langflow Assistant is restricted to administrators on this server."


def test_assistant_execution_allows_non_admin_when_policy_off():
    from types import SimpleNamespace

    from langflow.agentic.api.deps import require_agentic_component_admin

    with patch("lfx.services.deps.get_settings_service", return_value=_settings(admin_only=False)):
        assert require_agentic_component_admin(SimpleNamespace(is_superuser=False)) is None


def test_assistant_execution_allows_admin_when_policy_on():
    from types import SimpleNamespace

    from langflow.agentic.api.deps import require_agentic_component_admin

    with patch("lfx.services.deps.get_settings_service", return_value=_settings(admin_only=True)):
        assert require_agentic_component_admin(SimpleNamespace(is_superuser=True)) is None


def test_assistant_execution_denies_when_settings_unavailable():
    from types import SimpleNamespace

    from fastapi import HTTPException
    from langflow.agentic.api.deps import require_agentic_component_admin

    with patch("lfx.services.deps.get_settings_service", return_value=None), pytest.raises(HTTPException) as exc:
        require_agentic_component_admin(SimpleNamespace(is_superuser=False))

    assert exc.value.status_code == 403


# --- (b) execution gate: allow_custom_components -------------------------------------------------


async def test_validate_component_runtime_refuses_without_custom_components():
    """With allow_custom_components=false the code is never instantiated/executed."""
    from langflow.agentic.helpers import validation

    code = "class Foo:\n    pass\n"
    with (
        patch("lfx.services.deps.get_settings_service", return_value=_settings(allow_custom=False)),
        patch("lfx.custom.utils.build_custom_component_template") as mock_build,
    ):
        result = await validation.validate_component_runtime(code, user_id="u1")

    assert result is not None
    assert "disabled" in result.lower()
    assert mock_build.call_count == 0  # never reached the exec path


async def test_validate_component_runtime_attempts_build_when_allowed():
    """Sanity: with custom components allowed, it proceeds to the build/exec path."""
    from langflow.agentic.helpers import validation

    code = "class Foo:\n    pass\n"
    with (
        patch("lfx.services.deps.get_settings_service", return_value=_settings(allow_custom=True)),
        patch("lfx.custom.custom_component.component.Component"),
        patch("lfx.custom.utils.build_custom_component_template", return_value=(MagicMock(), MagicMock())),
        patch.object(validation, "_execute_output_methods_for_validation", new=AsyncMock(return_value=None)),
    ):
        result = await validation.validate_component_runtime(code, user_id="u1")

    assert result is None  # build path reached; no error


async def test_validate_component_runtime_refuses_unsafe_code_before_build():
    """The execution helper enforces the scanner even when called directly."""
    from langflow.agentic.helpers import validation

    code = "import os\nos.spawnv()\n"
    with (
        patch("lfx.services.deps.get_settings_service", return_value=_settings(allow_custom=True)),
        patch("lfx.custom.utils.build_custom_component_template") as mock_build,
    ):
        result = await validation.validate_component_runtime(code, user_id="u1")

    assert result is not None
    assert "security validation" in result.lower()
    mock_build.assert_not_called()


def test_overlay_skips_user_components_without_custom_components():
    """With allow_custom_components=false the overlay returns only the base registry (no exec)."""
    from langflow.agentic.services import user_components_overlay as overlay

    base = {"ChatInput": {}}
    with (
        patch.object(overlay, "load_local_registry", return_value=base),
        patch("lfx.services.deps.get_settings_service", return_value=_settings(allow_custom=False)),
        patch.object(overlay, "get_user_components_dir") as mock_dir,
        patch.object(overlay, "_build_overlay_entry") as mock_entry,
    ):
        result = overlay.load_registry_with_user_overlay(user_id="u1")

    assert result == base
    assert mock_dir.call_count == 0  # never walked the user's .components dir
    assert mock_entry.call_count == 0  # never built/executed an overlay entry
