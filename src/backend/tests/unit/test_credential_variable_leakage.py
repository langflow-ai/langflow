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
from pydantic import SecretStr, ValidationError

# Sentinel used as a stand-in for a "real" CREDENTIAL global variable's value.
# Tests assert this string never appears in error messages, attributes, or
# stringified output of any object derived from it.
_LEAKY_SECRET = "super-secret-value-XYZ"  # noqa: S105 — fixture sentinel.


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
async def test_credential_variable_in_password_field_is_masked_on_attribute():
    """A CREDENTIAL variable in a password field must remain masked.

    A CREDENTIAL global variable routed into a password (SecretStrInput) field
    is accepted, but the resulting component attribute is wrapped in SecretStr.
    Any path that stringifies the attribute (Message.text, status, traces, logs)
    surfaces the mask, not the raw value. Provider boundaries unwrap explicitly
    with `.get_secret_value()`.
    """

    class _PasswordFieldComponent(Component):
        display_name = "PasswordFieldTest"
        name = "PasswordFieldTest"
        inputs = [SecretStrInput(name="api_key", display_name="API Key")]
        outputs: list = []

    component = _PasswordFieldComponent(_user_id=str(uuid.uuid4()))

    resolved = await _resolve(
        component,
        params={"api_key": "MY_SECRET_VAR"},
        load_from_db_fields=["api_key"],
        get_variable_return=SecretStr(_LEAKY_SECRET),
    )

    component.set_attributes(resolved)
    api_key_attr = component._attributes["api_key"]

    assert isinstance(api_key_attr, SecretStr)
    assert str(api_key_attr) == "**********"
    assert _LEAKY_SECRET not in str(api_key_attr)
    assert _LEAKY_SECRET not in repr(api_key_attr)
    assert api_key_attr.get_secret_value() == _LEAKY_SECRET


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
