# Test this:
from langflow.interface.custom_types import PythonFunction
from langflow.utils import constants
import pytest


def test_python_function():
    """Test Python function"""
    func = PythonFunction(code=constants.DEFAULT_PYTHON_FUNCTION)
    assert func.get_function()("text") == "text"
    # the tool decorator should raise an error if
    # the function is not str -> str

    # This raises ValidationError
    with pytest.raises(SyntaxError):
        func = PythonFunction(code=pytest.CODE_WITH_SYNTAX_ERROR)
