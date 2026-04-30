"""Regression tests for https://github.com/langflow-ai/langflow/pull/12908.

Original repro: a CREDENTIAL-typed global variable routed into a non-password
input field (e.g. TextInputComponent.input_value, a MultilineInput) leaked the
raw value into the Component Output panel, traces, and logs.

These tests exercise the full chain that the bug touches:
  * `VariableService.get_variable` returns `pydantic.SecretStr` for CREDENTIAL
    variables (mocked here so the tests don't need a live DB).
  * `update_params_with_load_from_db_fields` propagates the SecretStr through
    variable resolution.
  * Field validators on text/numeric inputs reject SecretStr in non-password
    fields with an actionable error.
  * Component-level `_wrap_if_secret` keeps password-bound attributes wrapped
    so any stringification path (Message.text, status, traces, logs) renders
    `'**********'` instead of the secret.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.input_output import TextInputComponent
from lfx.custom import Component
from lfx.inputs.inputs import SecretStrInput
from lfx.interface.initialize.loading import update_params_with_load_from_db_fields
from lfx.io import Output
from lfx.schema.message import Message
from pydantic import SecretStr, ValidationError

# Sentinel used as a stand-in for a "real" CREDENTIAL global variable's value.
# Tests assert this string never appears in error messages, attributes, or
# stringified output of any object derived from it.
_LEAKY_SECRET = "super-secret-value-XYZ"  # noqa: S105 — fixture sentinel.  # pragma: allowlist secret


def _patch_resolution(get_variable_return):
    """Wire up the minimum scaffolding around `update_params_with_load_from_db_fields`.

    Returns a context-manager-ish tuple of (session_scope_patcher, settings_patcher,
    get_variable_async_mock). The settings patch ensures the loading module takes
    the DB path (not the noop env-var path).
    """
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    session_patcher = patch("lfx.interface.initialize.loading.session_scope")
    settings_patcher = patch("lfx.services.deps.get_settings_service")
    get_variable_mock = AsyncMock(return_value=get_variable_return)
    return session_patcher, settings_patcher, mock_session, get_variable_mock


async def _resolve(component, params, load_from_db_fields, get_variable_return):
    session_patcher, settings_patcher, mock_session, get_variable_mock = _patch_resolution(get_variable_return)
    component.get_variable = get_variable_mock
    with session_patcher as mock_session_scope, settings_patcher as mock_get_settings:
        mock_session_scope.return_value = mock_session
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = False
        mock_get_settings.return_value = mock_settings_service
        return await update_params_with_load_from_db_fields(
            component, params, load_from_db_fields, fallback_to_env_vars=False
        )


@pytest.mark.asyncio
async def test_credential_variable_does_not_leak_into_text_input_output():
    """A CREDENTIAL variable must not leak into text input output.

    * keep the value wrapped as SecretStr through variable resolution
    * never surface the raw value via str()/repr()
    * fail Pydantic validation when assigned to the non-password field, with a
      clear error message that itself does not contain the secret
    """
    component = TextInputComponent(_user_id=str(uuid.uuid4()))

    resolved = await _resolve(
        component,
        params={"input_value": "MY_SECRET_VAR"},
        load_from_db_fields=["input_value"],
        get_variable_return=SecretStr(_LEAKY_SECRET),
    )

    # Variable resolution must preserve the SecretStr wrapper end-to-end.
    resolved_value = resolved["input_value"]
    assert isinstance(resolved_value, SecretStr)
    assert resolved_value.get_secret_value() == _LEAKY_SECRET
    assert str(resolved_value) == "**********"
    assert _LEAKY_SECRET not in str(resolved_value)
    assert _LEAKY_SECRET not in repr(resolved_value)

    # set_attributes routes through input validation; the non-password field rejects.
    with pytest.raises(ValidationError) as excinfo:
        component.set_attributes(resolved)

    error_text = str(excinfo.value)
    assert "Credential-typed global variable" in error_text
    assert "input_value" in error_text
    # The error message itself must not echo the underlying secret.
    assert _LEAKY_SECRET not in error_text


@pytest.mark.asyncio
async def test_credential_variable_in_password_field_preserves_runtime_string_contract():
    """A CREDENTIAL variable in a password field remains usable as a string.

    A CREDENTIAL global variable routed into a password (SecretStrInput) field
    is accepted. The runtime component attribute is unwrapped for compatibility
    with existing provider-client code, while component output/log boundaries
    still sanitize the recorded secret value.
    """

    class _PasswordFieldComponent(Component):
        display_name = "PasswordFieldTest"
        name = "PasswordFieldTest"
        inputs = [SecretStrInput(name="api_key", display_name="API Key")]
        outputs = [Output(display_name="Output", name="output", method="build_output")]

        def build_output(self) -> Message:
            self.log(self.api_key)
            self.status = self.api_key
            return Message(text=self.api_key)

    component = _PasswordFieldComponent(_user_id=str(uuid.uuid4()))

    resolved = await _resolve(
        component,
        params={"api_key": "MY_SECRET_VAR"},  # pragma: allowlist secret
        load_from_db_fields=["api_key"],
        get_variable_return=SecretStr(_LEAKY_SECRET),
    )

    component.set_attributes(resolved)
    api_key_attr = component._attributes["api_key"]

    assert api_key_attr == _LEAKY_SECRET
    assert component.api_key == _LEAKY_SECRET

    results, artifacts = await component._build_results()

    assert results["output"].text == "**********"
    assert results["output"].data["text"] == "**********"
    assert artifacts["output"]["raw"] == "**********"
    assert "**********" in artifacts["output"]["repr"]
    assert _LEAKY_SECRET not in artifacts["output"]["repr"]
    assert component._output_logs["output"][0].message == "**********"
    assert component.status == "**********"
    assert component.repr_value == "**********"


@pytest.mark.asyncio
async def test_generic_variable_still_flows_into_text_input():
    """GENERIC-typed variables must still flow into text input.

    Variables returned as plain str by VariableService must continue to work in
    non-password fields. Only CREDENTIAL-typed (SecretStr) values are blocked.
    """
    plain_value = "non-sensitive-display-name"
    component = TextInputComponent(_user_id=str(uuid.uuid4()))

    resolved = await _resolve(
        component,
        params={"input_value": "MY_GENERIC_VAR"},
        load_from_db_fields=["input_value"],
        get_variable_return=plain_value,
    )

    component.set_attributes(resolved)
    assert component._attributes["input_value"] == plain_value


@pytest.mark.asyncio
async def test_credential_variable_accepted_when_use_global_variable_toggled_on():
    """Credential variable is accepted when 'Use Global Variable' toggle is on.

    Toggling on TextInput re-types `input_value` via `update_build_config` to
    `password=True, multiline=False`. A CREDENTIAL-typed variable must then be
    accepted by validation, since the field is now a secret field. The original
    bug: validation rejected it regardless of `password`, because
    `MultilineInput` declares `password` after the inherited `value` field, so
    the field-level check on `value` ran before `password` was populated in
    `info.data`.
    """
    from lfx.inputs.inputs import MultilineInput

    field = MultilineInput(name="input_value", value=SecretStr(_LEAKY_SECRET), password=True)
    assert isinstance(field.value, SecretStr)
    assert field.value.get_secret_value() == _LEAKY_SECRET

    # And: with password=False (default), the same value is rejected.
    with pytest.raises(ValidationError) as excinfo:
        MultilineInput(name="input_value", value=SecretStr(_LEAKY_SECRET))
    assert "Credential-typed global variable" in str(excinfo.value)
    assert "input_value" in str(excinfo.value)
    assert _LEAKY_SECRET not in str(excinfo.value)
