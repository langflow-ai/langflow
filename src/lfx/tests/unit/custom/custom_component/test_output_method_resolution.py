from types import SimpleNamespace

import pytest
from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output


class _TemplateComponent(Component):
    """Stands in for a component class that does not define the saved node's output method."""

    display_name = "Format Answer"
    name = "FormatAnswer"
    outputs = [Output(name="output", display_name="Output", method="build_output")]

    def build_output(self) -> str:
        return "template"


class _OverriddenRunComponent(Component):
    display_name = "Overridden Run"
    name = "OverriddenRun"
    outputs = [Output(name="result", display_name="Result", method="run")]

    def run(self) -> str:
        return "executed"


def _with_saved_output(method: str) -> Component:
    """Apply a saved node's outputs the way a graph vertex does (vertex outputs override the class)."""
    component = _TemplateComponent()
    saved_output = {"name": "answer", "display_name": "Answer", "method": method, "types": ["Message"]}
    component._vertex = SimpleNamespace(outputs=[saved_output], outgoing_edges=[])
    component.map_outputs()
    return component


def _record_send_error(component: Component) -> list:
    calls: list = []
    original = component.send_error

    async def _recording_send_error(*args, **kwargs):
        calls.append(kwargs.get("exception"))
        return await original(*args, **kwargs)

    component.send_error = _recording_send_error
    return calls


@pytest.mark.asyncio
async def test_should_fail_once_when_output_method_reenters_component_run():
    component = _with_saved_output("run")
    errors = _record_send_error(component)

    with pytest.raises(RuntimeError) as exc_info:
        await component.run()

    assert not isinstance(exc_info.value, RecursionError)
    assert '"Format Answer"' in str(exc_info.value)
    assert '"run"' in str(exc_info.value)
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_should_name_display_name_when_output_method_is_missing():
    component = _with_saved_output("build_answer")
    errors = _record_send_error(component)

    with pytest.raises(AttributeError) as exc_info:
        await component.run()

    assert '"Format Answer"' in str(exc_info.value)
    assert '"build_answer"' in str(exc_info.value)
    assert "_TemplateComponent" not in str(exc_info.value)
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_should_run_output_method_named_run_when_component_defines_it():
    component = _OverriddenRunComponent()

    results, _artifacts = await component._build_results()

    assert results["result"] == "executed"


class _NestedOutputComponent(Component):
    display_name = "Nested Outputs"
    name = "NestedOutputs"
    outputs = [
        Output(name="outer", display_name="Outer", method="build_outer"),
        Output(name="inner", display_name="Inner", method="build_inner"),
    ]

    async def build_outer(self) -> str:
        await self._get_output_result(self._outputs_map["inner"])
        return await self.run()

    def build_inner(self) -> str:
        return "inner"


@pytest.mark.asyncio
async def test_should_keep_reentry_guard_after_a_nested_output_resolves():
    component = _NestedOutputComponent()
    errors = _record_send_error(component)

    with pytest.raises(RuntimeError) as exc_info:
        await component.run()

    assert not isinstance(exc_info.value, RecursionError)
    assert '"outer"' in str(exc_info.value)
    assert len(errors) == 1
