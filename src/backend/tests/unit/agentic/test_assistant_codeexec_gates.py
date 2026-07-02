"""Security gates on the agentic assistant's in-process code-execution path (Issue 15).

The assistant generates component code and EXECUTES it in-process (validate_component_runtime ->
build_custom_component_template -> compile/exec; and again in the user-components overlay). These
tests assert the two hardening gates:
  (a) the agentic endpoints are unreachable (404) unless agentic_experience is enabled;
  (b) the execution entry points refuse when allow_custom_components is disabled.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _settings(*, allow_custom=True, agentic=True):
    s = MagicMock()
    s.settings.allow_custom_components = allow_custom
    s.settings.agentic_experience = agentic
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
