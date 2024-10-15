from langflow.components import prototypes


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
