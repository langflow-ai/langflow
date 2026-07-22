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
from lfx.inputs.inputs import IntInput, SecretStrInput, StrInput
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
async def test_secret_inputs_are_redacted_at_tracing_boundary_by_field_metadata():
    """Secret input metadata, not field-name guesses, controls trace redaction."""

    class _TraceSecretsComponent(Component):
        display_name = "TraceSecretsTest"
        name = "TraceSecretsTest"
        inputs = [
            SecretStrInput(name="aws_secret_access_key", display_name="AWS Secret Access Key"),
            SecretStrInput(name="access_token", display_name="Access Token"),
            IntInput(name="token_budget", display_name="Token Budget"),
            StrInput(name="region", display_name="Region"),
        ]
        outputs = [Output(display_name="Output", name="output", method="build_output")]

        def build_output(self) -> str:
            return self.region

    component = _TraceSecretsComponent(_user_id=str(uuid.uuid4()))
    component.set_attributes(
        {
            "aws_secret_access_key": "aws-secret-sentinel",  # pragma: allowlist secret
            "access_token": "token-secret-sentinel",  # pragma: allowlist secret
            "token_budget": 4096,
            "region": "us-west-2",
        }
    )

    tracing_service = MagicMock()
    trace_context = MagicMock()
    trace_context.__aenter__ = AsyncMock(return_value=tracing_service)
    trace_context.__aexit__ = AsyncMock(return_value=None)
    tracing_service.trace_component.return_value = trace_context
    component._tracing_service = tracing_service

    await component._build_with_tracing()

    traced_inputs = tracing_service.trace_component.call_args.args[2]
    assert traced_inputs == {
        "aws_secret_access_key": "**********",
        "access_token": "**********",
        "token_budget": 4096,
        "region": "us-west-2",
    }


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


@pytest.mark.asyncio
async def test_secret_value_reaches_connected_component_unmasked_but_masked_for_display():
    """Regression for https://github.com/langflow-ai/langflow/issues/14152.

    Masking must apply only to human-facing surfaces (results / artifacts / status /
    logs), never to ``output.value`` -- the object a connected downstream component
    reads when resolving a graph edge (``ComponentVertex._get_result`` prefers
    ``output.value`` over the ``results`` dict). A component that legitimately embeds a
    real secret in its output (e.g. a connection string) must hand the *real* value to
    its connected consumer while still masking every displayed copy.
    """

    class _BuildConnectionString(Component):
        display_name = "BuildConnectionString"
        name = "BuildConnectionString"
        inputs = [SecretStrInput(name="password", display_name="Password")]
        outputs = [Output(display_name="Connection String", name="conn_string", method="build_conn_string")]

        def build_conn_string(self) -> Message:
            return Message(text=f"postgresql://demo_user:{self.password}@localhost:5432/demo_db")

    component = _BuildConnectionString(_user_id=str(uuid.uuid4()))
    component.set_attributes({"password": "hunter2"})  # pragma: allowlist secret

    results, artifacts = await component._build_results()

    real = "postgresql://demo_user:hunter2@localhost:5432/demo_db"  # pragma: allowlist secret
    masked = "postgresql://demo_user:**********@localhost:5432/demo_db"

    # (a) The value delivered on a graph edge (``output.value``) is the REAL secret.
    edge_value = component._outputs_map["conn_string"].value
    assert edge_value.text == real
    assert "hunter2" in edge_value.text  # pragma: allowlist secret

    # (b) Every human-facing copy is masked (preserves the guarantee from #12908).
    assert results["conn_string"].text == masked
    assert artifacts["conn_string"]["raw"] == masked
    assert "**********" in artifacts["conn_string"]["repr"]
    assert "hunter2" not in artifacts["conn_string"]["repr"]  # pragma: allowlist secret

    # The masked, serialized copy must be an independent object -- not the edge value.
    assert results["conn_string"] is not edge_value


@pytest.mark.asyncio
async def test_sanitize_secret_values_returns_masked_copy_without_mutating_source():
    """`_sanitize_secret_values` must be non-mutating.

    It returns a masked copy and leaves the source ``Message`` (and therefore
    ``output.value``) untouched. Regression for #14152: the previous in-place mutation
    of ``Message.text`` / ``Data.data`` is what corrupted the edge value.
    """

    class _Noop(Component):
        display_name = "Noop"
        name = "Noop"
        inputs = [SecretStrInput(name="password", display_name="Password")]
        outputs = [Output(display_name="Output", name="output", method="build_output")]

        def build_output(self) -> Message:
            return Message(text="unused")

    component = _Noop(_user_id=str(uuid.uuid4()))
    component.set_attributes({"password": "hunter2"})  # pragma: allowlist secret

    original = Message(text="token=hunter2")  # pragma: allowlist secret
    masked = component._sanitize_secret_values(original)

    assert masked is not original
    assert masked.text == "token=**********"
    # Source is unchanged -- this is what a connected downstream component would receive.
    assert original.text == "token=hunter2"  # pragma: allowlist secret
