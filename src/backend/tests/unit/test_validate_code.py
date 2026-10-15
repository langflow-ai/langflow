import sys
from pathlib import Path
from unittest import mock

import pytest
from langflow.utils.validate import (
    create_class,
    create_function,
    execute_function,
    extract_function_name,
    validate_code,
)
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


def test_validate_code_does_not_execute_imported_modules(tmp_path, monkeypatch):
    """H1-3992099: validate_code must locate imports without executing them.

    A module planted on a writable sys.path entry must not run its top-level
    code when "validated" — importlib.import_module() executed it; find_spec()
    does not.
    """
    marker = tmp_path / "planted_module_executed.txt"
    (tmp_path / "planted_validate_rce.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "planted_validate_rce", raising=False)

    errors = validate_code("import planted_validate_rce")

    assert errors == {"imports": {"errors": []}, "function": {"errors": []}}
    assert not marker.exists()

    # The same import through importlib DOES execute the module, proving the
    # marker path is live and the control above is meaningful.
    import importlib

    importlib.import_module("planted_validate_rce")
    assert marker.exists()


def test_validate_code_does_not_import_parent_packages(tmp_path, monkeypatch):
    """find_spec() on a dotted name would import (execute) parent packages.

    validate_code must only resolve the top-level package.
    """
    marker = tmp_path / "planted_parent_executed.txt"
    package = tmp_path / "planted_parent_pkg"
    package.mkdir()
    (package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    (package / "child.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "planted_parent_pkg", raising=False)

    errors = validate_code("import planted_parent_pkg.child")

    assert errors == {"imports": {"errors": []}, "function": {"errors": []}}
    assert not marker.exists()


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


def test_create_class():
    code = """
from langflow.custom import CustomComponent

class ExternalClass:
    def __init__(self, value):
        self.value = value

class MyComponent(CustomComponent):
    def build(self):
        return ExternalClass("test")
"""
    class_name = "MyComponent"
    created_class = create_class(code, class_name)
    instance = created_class()
    result = instance.build()
    assert result.value == "test"


def test_create_class_module_import():
    code = """
from langflow.custom import CustomComponent
from PIL import ImageDraw

class ExternalClass:
    def __init__(self, value):
        self.value = value

class MyComponent(CustomComponent):
    def build(self):
        return ExternalClass("test")
"""
    class_name = "MyComponent"
    created_class = create_class(code, class_name)
    instance = created_class()
    result = instance.build()
    assert result.value == "test"


def test_create_class_with_multiple_external_classes():
    code = """
from langflow.custom import CustomComponent

class ExternalClass1:
    def __init__(self, value):
        self.value = value

class ExternalClass2:
    def __init__(self, value):
        self.value = value

class MyComponent(CustomComponent):
    def build(self):
        return ExternalClass1("test1"), ExternalClass2("test2")
"""
    class_name = "MyComponent"
    created_class = create_class(code, class_name)
    instance = created_class()
    result1, result2 = instance.build()
    assert result1.value == "test1"
    assert result2.value == "test2"


def test_create_class_with_external_variables_and_functions():
    code = """
from langflow.custom import CustomComponent

external_variable = "external_value"

def external_function():
    return "external_function_value"

class MyComponent(CustomComponent):
    def build(self):
        return external_variable, external_function()
"""
    class_name = "MyComponent"
    created_class = create_class(code, class_name)
    instance = created_class()
    result_variable, result_function = instance.build()
    assert result_variable == "external_value"
    assert result_function == "external_function_value"
