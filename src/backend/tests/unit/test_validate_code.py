from pathlib import Path
from unittest import mock

import pytest
from langflow.utils.validate import create_function, execute_function, extract_function_name, validate_code
from requests.exceptions import MissingSchema


def test_create_function():
    code = """
from pathlib import Path

def my_function(x: str) -> Path:
    return Path(x)
"""

    function_name = extract_function_name(code)
    function = create_function(code, function_name)
    result = function("test")
    assert result == Path("test")


def test_validate_code():
    # Test case with a valid import and function
    code1 = """
import math

def square(x):
    return x ** 2
"""
    errors1 = validate_code(code1)
    assert errors1 == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with an invalid import and valid function
    code2 = """
import non_existent_module

def square(x):
    return x ** 2
"""
    errors2 = validate_code(code2)
    assert errors2 == {
        "imports": {"errors": ["No module named 'non_existent_module'"]},
        "function": {"errors": []},
    }

    # Test case with a valid import and invalid function syntax
    code3 = """
import math

def square(x)
    return x ** 2
"""
    errors3 = validate_code(code3)
    assert errors3 == {
        "imports": {"errors": []},
        "function": {"errors": ["expected ':' (<unknown>, line 4)"]},
    }


def test_execute_function_success():
    code = """
import math

def my_function(x):
    return math.sin(x) + 1
    """
    result = execute_function(code, "my_function", 0.5)
    assert result == 1.479425538604203


def test_execute_function_missing_module():
    code = """
import some_missing_module

def my_function(x):
    return some_missing_module.some_function(x)
    """
    with pytest.raises(ModuleNotFoundError):
        execute_function(code, "my_function", 0.5)


def test_execute_function_missing_function():
    code = """
import math

def my_function(x):
    return math.some_missing_function(x)
    """
    with pytest.raises(AttributeError):
        execute_function(code, "my_function", 0.5)


def test_execute_function_missing_schema():
    code = """
import requests

def my_function(x):
    return requests.get(x).text
    """
    with mock.patch("requests.get", side_effect=MissingSchema), pytest.raises(MissingSchema):
        execute_function(code, "my_function", "invalid_url")
