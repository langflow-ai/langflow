from langflow.components import experimental


def test_python_function_component():
    # Arrange
    python_function_component = experimental.PythonFunctionComponent()

    # Act
    # function must be a string representation
    function = "def function():\n    return 'Hello, World!'"
    # result is the callable function
    result = python_function_component.build(function)

    # Assert
    assert result() == "Hello, World!"
