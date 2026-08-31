import pytest
from lfx.components import prototypes
from lfx.services.deps import get_settings_service
from lfx.utils.python_repl_security import CodeExecutionDisabledError


def test_python_function_component():
    # Arrange
    python_function_component = prototypes.PythonFunctionComponent()

    # Act
    # function must be a string representation
    function = "def function():\n    return 'Hello, World!'"
    python_function_component.function_code = function
    # result is the callable function
    result = python_function_component.get_function_callable()
    result_message = python_function_component.execute_function_message()
    result_data = python_function_component.execute_function_data()

    # Assert
    assert result() == "Hello, World!"
    assert result_message.text == "Hello, World!"
    assert result_data[0].text == "Hello, World!"


def test_python_function_component_respects_code_execution_policy(monkeypatch):
    component = prototypes.PythonFunctionComponent()
    component.function_code = "def function():\n    return 'unsafe'"
    monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", False)

    with pytest.raises(CodeExecutionDisabledError):
        component.get_function_callable()
    with pytest.raises(CodeExecutionDisabledError):
        component.execute_function()
