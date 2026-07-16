from copy import deepcopy

import pytest
from lfx.components.input_output import ChatInput
from lfx.inputs.inputs import BoolInput


def _build_config() -> dict:
    return {input_.name: input_.to_dict() for input_ in ChatInput.inputs}


def test_chat_input_exposes_global_variable_mode() -> None:
    """Chat Input must preserve the global-variable mode of the legacy Text Input."""
    global_variable_input = next(input_ for input_ in ChatInput.inputs if input_.name == "use_global_variable")

    assert isinstance(global_variable_input, BoolInput)
    assert global_variable_input.value is False
    assert global_variable_input.advanced is True
    assert global_variable_input.real_time_refresh is True


@pytest.mark.parametrize(
    ("enabled", "expected_multiline", "expected_password"),
    [(True, False, True), (False, True, False)],
)
def test_chat_input_global_variable_mode_updates_input_field(enabled, expected_multiline, expected_password) -> None:
    component = ChatInput()
    build_config = _build_config()

    updated_config = component.update_build_config(
        deepcopy(build_config),
        field_value=enabled,
        field_name="use_global_variable",
    )

    assert updated_config["input_value"]["multiline"] is expected_multiline
    assert updated_config["input_value"]["password"] is expected_password


def test_chat_input_global_variable_mode_ignores_other_fields() -> None:
    component = ChatInput()
    build_config = _build_config()

    updated_config = component.update_build_config(
        deepcopy(build_config),
        field_value="User",
        field_name="sender_name",
    )

    assert updated_config == build_config
