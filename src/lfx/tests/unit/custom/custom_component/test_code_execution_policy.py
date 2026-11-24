from types import SimpleNamespace

import pytest
from langchain_core.tools import ToolException
from lfx.base.tools.component_tool import _build_output_async_function, _build_output_function
from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output
from lfx.utils.python_repl_security import CodeExecutionDisabledError


class _OutputComponent(Component):
    display_name = "Safe Fixture"
    name = "SafeFixture"
    outputs = [Output(name="result", display_name="Result", method="run")]

    def run(self) -> str:
        return "executed"


class LambdaFilterComponent(_OutputComponent):
    """Match a registered component through its Python class name."""


class _CSVAgentFixture(_OutputComponent):
    """Match a registered component through its component name."""

    name = "CSVAgent"


class _CodeActFixture(_OutputComponent):
    """Match a registered component through its display name."""

    display_name = "CodeAct Agent (Smolagents)"


class _AsyncCSVAgentFixture(Component):
    display_name = "CSV Agent Fixture"
    name = "CSVAgent"
    outputs = [Output(name="result", display_name="Result", method="run")]

    async def run(self) -> str:
        return "executed"


def _set_security_settings(monkeypatch, *, allow_custom: bool, block_code_execution: bool = False) -> SimpleNamespace:
    settings = SimpleNamespace(
        allow_custom_components=allow_custom,
        block_code_interpreter_components=block_code_execution,
    )
    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=settings),
    )
    return settings


@pytest.mark.asyncio
@pytest.mark.parametrize("component_class", [LambdaFilterComponent, _CSVAgentFixture, _CodeActFixture])
async def test_registered_code_execution_components_are_blocked_at_runtime(monkeypatch, component_class):
    _set_security_settings(monkeypatch, allow_custom=False)

    with pytest.raises(CodeExecutionDisabledError, match="allow_custom_components"):
        await component_class()._build_results()


@pytest.mark.asyncio
async def test_unregistered_component_is_allowed_at_runtime(monkeypatch):
    _set_security_settings(monkeypatch, allow_custom=False)

    results, _ = await _OutputComponent()._build_results()

    assert results == {"result": "executed"}


@pytest.mark.asyncio
async def test_registered_component_is_allowed_when_code_execution_is_enabled(monkeypatch):
    _set_security_settings(monkeypatch, allow_custom=True)

    results, _ = await _CSVAgentFixture()._build_results()

    assert results == {"result": "executed"}


@pytest.mark.asyncio
async def test_registered_component_is_blocked_by_code_interpreter_policy(monkeypatch):
    _set_security_settings(monkeypatch, allow_custom=True, block_code_execution=True)

    with pytest.raises(CodeExecutionDisabledError, match="block_code_interpreter_components"):
        await _CSVAgentFixture()._build_results()


def test_registered_code_execution_component_is_blocked_in_sync_tool_mode(monkeypatch):
    settings = _set_security_settings(monkeypatch, allow_custom=True)
    component = _CSVAgentFixture()
    tool_function = _build_output_function(component, component.run)
    settings.allow_custom_components = False

    with pytest.raises(ToolException, match="allow_custom_components"):
        tool_function()


@pytest.mark.asyncio
async def test_registered_code_execution_component_is_blocked_in_async_tool_mode(monkeypatch):
    _set_security_settings(monkeypatch, allow_custom=False)
    component = _AsyncCSVAgentFixture()
    tool_function = _build_output_async_function(component, component.run)

    with pytest.raises(ToolException, match="allow_custom_components"):
        await tool_function()
