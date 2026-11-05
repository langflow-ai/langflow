"""Definition-time callables must pass security scanning before component construction."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langflow.agentic.helpers.code_security import scan_code_security
from langflow.agentic.helpers.validation import validate_component_runtime


@pytest.mark.parametrize("definition", ["class Generated:", "def build():", "async def build():"])
@pytest.mark.parametrize(
    ("setup", "decorator"),
    [
        ("", "open"),
        ("", "eval"),
        ("import builtins", "builtins.open"),
        ("import io as streams", "streams.open"),
        ("reader = open", "reader"),
        ("", "(open if condition else str)"),
        ("", "({'reader': open}['reader'])"),
    ],
)
def test_rejects_restricted_implicit_decorator_calls(setup: str, decorator: str, definition: str) -> None:
    result = scan_code_security(f"{setup}\n@{decorator}\n{definition}\n    pass")
    assert not result.is_safe
    assert any("forbidden" in violation for violation in result.violations)


@pytest.mark.parametrize(
    ("setup", "keywords"),
    [
        ("", "metaclass=open"),
        ("", "metaclass=eval"),
        ("import builtins", "metaclass=builtins.open"),
        ("import io as streams", "metaclass=streams.open"),
        ("reader = open", "metaclass=reader"),
        ("", "metaclass=(open if condition else type)"),
        ("", "metaclass={'reader': open}['reader']"),
        ("", "**{'metaclass': open}"),
        ("", "reader=open"),
    ],
)
def test_rejects_restricted_class_keyword_values(setup: str, keywords: str) -> None:
    result = scan_code_security(f"{setup}\nclass Generated({keywords}):\n    pass")
    assert not result.is_safe
    assert any("forbidden" in violation for violation in result.violations)


@pytest.mark.parametrize(
    "code",
    [
        "@open('synthetic-input')\nclass Generated:\n    pass",
        "@eval('synthetic-input')\ndef build():\n    pass",
        "class Generated(metaclass=open('synthetic-input')):\n    pass",
        "class Generated(reader=open('synthetic-input')):\n    pass",
    ],
)
def test_rejects_explicit_calls_in_definition_expressions(code: str) -> None:
    assert not scan_code_security(code).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "from dataclasses import dataclass\n@dataclass\nclass Generated:\n    value: str",
        "from functools import lru_cache\n@lru_cache(maxsize=4)\ndef build():\n    return 'safe'",
        "class Generated:\n    @staticmethod\n    def build():\n        return 'safe'",
        "class Generated:\n    @property\n    def value(self):\n        return 'safe'",
        "def decorate(value):\n    return value\n@decorate\nclass Generated:\n    pass",
        "class Meta(type):\n    pass\nclass Generated(metaclass=Meta):\n    pass",
        "class Generated(metaclass=type, label='safe'):\n    pass",
        "class Generated(**{'metaclass': type}):\n    pass",
        "def open(value):\n    return value\n@open\nclass Generated:\n    pass",
        "def open(name, bases, namespace):\n    return type(name, bases, namespace)\n"
        "class Generated(metaclass=open):\n    pass",
    ],
)
def test_preserves_safe_definition_expressions(code: str) -> None:
    assert scan_code_security(code).is_safe


@pytest.mark.parametrize(
    "code",
    [
        "@open\nclass Generated:\n    pass",
        "class Generated:\n    @open\n    def build(self):\n        pass",
        "class Generated(metaclass=open):\n    pass",
    ],
)
async def test_runtime_validation_refuses_unsafe_definitions_before_construction(monkeypatch, code: str) -> None:
    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True)),
    )
    builder = MagicMock(side_effect=AssertionError("unsafe code reached component construction"))
    monkeypatch.setattr("lfx.custom.utils.build_custom_component_template", builder)

    result = await validate_component_runtime(code, user_id="test-user")

    assert result is not None
    assert "failed security validation" in result
    builder.assert_not_called()
