# Test this:
from langflow.interface.importing.utils import get_function
import pytest
from langflow.interface.tools.custom import PythonFunctionTool, PythonFunction
from langflow.utils import constants


def test_python_function_tool():
    """Test Python function"""
    code = constants.DEFAULT_PYTHON_FUNCTION
    func = get_function(code)
    func = PythonFunctionTool(name="Test", description="Testing", code=code, func=func)
    assert func("text") == "text"
    # the tool decorator should raise an error if
    # the function is not str -> str

    # This raises ValidationError
    with pytest.raises(SyntaxError):
        code = pytest.CODE_WITH_SYNTAX_ERROR
        func = get_function(code)
        func = PythonFunctionTool(
            name="Test", description="Testing", code=code, func=func
        )


def test_python_function():
    """Test Python function"""
    func = PythonFunction(code=constants.DEFAULT_PYTHON_FUNCTION)
    assert get_function(func.code)("text") == "text"
    # the tool decorator should raise an error if
    # the function is not str -> str

    # This raises ValidationError
    with pytest.raises(SyntaxError):
        func = PythonFunction(code=pytest.CODE_WITH_SYNTAX_ERROR)
