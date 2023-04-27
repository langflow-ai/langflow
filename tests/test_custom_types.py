# Test this:
import pytest
from langflow.interface.tools.custom import PythonFunction
from langflow.utils import constants


def test_python_function():
    """Test Python function"""
    func = PythonFunction(code=constants.DEFAULT_PYTHON_FUNCTION)
    assert func.get_function()("text") == "text"
    # the tool decorator should raise an error if
    # the function is not str -> str

    # This raises ValidationError
    with pytest.raises(SyntaxError):
        func = PythonFunction(code=pytest.CODE_WITH_SYNTAX_ERROR)
