"""A source file that defines several Component subclasses must resolve to the intended class.

Custom components store their whole containing file as ``code``, so every node
built from a multi-class file carries the same source. Picking "the first
Component subclass" made each of them silently become the first class.
"""

import importlib.util
import sys
from textwrap import dedent
from types import SimpleNamespace

import pytest
from lfx.custom.custom_component.component import Component
from lfx.custom.eval import eval_custom_component_code
from lfx.custom.utils import build_custom_component_template, create_component_template
from lfx.custom.validate import extract_class_name
from lfx.graph import Graph
from lfx.graph.flow_builder.component import add_component
from lfx.interface.initialize import loading

MULTI_COMPONENT_SOURCE = dedent(
    """
    from lfx.custom.custom_component.component import Component
    from lfx.io import Output
    from lfx.schema.data import Data


    class First(Component):
        display_name = "First"
        name = "First"
        outputs = [Output(display_name="Out", name="out", method="run")]

        def run(self) -> Data:
            return Data(data={"which": "First"})


    class Second(Component):
        display_name = "Second"
        name = "Second"
        outputs = [Output(display_name="Out2", name="out2", method="run2")]

        def run2(self) -> Data:
            return Data(data={"which": "Second"})
    """
)


def test_should_select_requested_class_when_source_defines_several_components():
    assert extract_class_name(MULTI_COMPONENT_SOURCE, "Second") == "Second"


def test_should_keep_first_class_when_no_class_is_requested():
    assert extract_class_name(MULTI_COMPONENT_SOURCE) == "First"


def test_should_fall_back_to_first_class_when_requested_class_is_not_in_source():
    assert extract_class_name(MULTI_COMPONENT_SOURCE, "NotInThisFile") == "First"


def test_should_select_requested_subclass_of_a_component_defined_in_the_same_file():
    code = dedent(
        """
        class SharedBase(Component):
            pass

        class Concrete(SharedBase):
            pass
        """
    )

    assert extract_class_name(code, "Concrete") == "Concrete"
    assert extract_class_name(code) == "SharedBase"


def test_should_ignore_requested_name_when_it_is_not_a_component_class():
    code = dedent(
        """
        class Helper:
            pass

        class OnlyComponent(Component):
            pass
        """
    )

    assert extract_class_name(code, "Helper") == "OnlyComponent"


def test_should_evaluate_requested_class_from_multi_component_source():
    assert eval_custom_component_code(MULTI_COMPONENT_SOURCE, class_name="Second").__name__ == "Second"


@pytest.fixture
def multi_component_module(tmp_path, monkeypatch):
    module_name = "multi_component_source_fixture"
    module_path = tmp_path / f"{module_name}.py"
    module_path.write_text(MULTI_COMPONENT_SOURCE, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def test_should_build_palette_template_from_the_loaded_class_not_the_first_in_file(multi_component_module):
    template, _ = create_component_template(component_extractor=multi_component_module.Second())

    assert template["display_name"] == "Second"
    assert [output["name"] for output in template["outputs"]] == ["out2"]
    assert template["metadata"]["component_class_name"] == "Second"


@pytest.mark.parametrize(("class_name", "expected"), [("Second", "Second"), (None, "First"), ("Missing", "First")])
def test_should_preserve_class_when_rebuilding_template_from_code(class_name, expected):
    template, instance = build_custom_component_template(Component(_code=MULTI_COMPONENT_SOURCE), class_name=class_name)

    assert type(instance).__name__ == expected
    assert template["display_name"] == expected
    assert template["metadata"]["component_class_name"] == expected


@pytest.mark.parametrize(
    ("registry_type", "saved_class"),
    [("Second", None), ("ext:my_bundle:Second@extra", None), (None, "Second"), ("First", "Second")],
)
async def test_should_restore_flow_builder_custom_component_identity(
    multi_component_module, registry_type, saved_class
):
    template, _ = create_component_template(component_extractor=multi_component_module.Second())
    if saved_class is None:
        template["metadata"].pop("component_class_name")
    flow = {"data": {"nodes": [], "edges": []}}
    add_component(flow, "Second", {"Second": {**template, "custom": True}}, component_id="Second-abc12")
    if registry_type is None:
        flow["data"]["nodes"][0]["data"].pop("_flow_builder_registry_type")
    else:
        flow["data"]["nodes"][0]["data"]["_flow_builder_registry_type"] = registry_type

    assert flow["data"]["nodes"][0]["data"]["type"] == "CustomComponent"
    graph = Graph.from_payload(flow)
    results = [result async for result in graph.async_start()]

    assert type(graph.get_vertex("Second-abc12").custom_component).__name__ == "Second"
    assert results[0].result_dict.artifacts["out2"]["raw"] == {"which": "Second"}


@pytest.mark.parametrize("vertex_type", ["ext:my_bundle:Second@extra", "Second"])
async def test_should_rebuild_node_from_stored_source_as_its_own_class(vertex_type):
    vertex = SimpleNamespace(
        vertex_type=vertex_type,
        base_type="component",
        params={"code": MULTI_COMPONENT_SOURCE},
        id="Second-abc12",
        outputs=[],
    )

    component, _ = loading.instantiate_class(vertex)

    assert type(component).__name__ == "Second"
    assert component.run2().data == {"which": "Second"}


async def test_should_rebuild_tool_mode_node_as_its_own_class():
    vertex = SimpleNamespace(
        vertex_type="Component",
        data={"type": "ext:my_bundle:Second@extra"},
        base_type="component",
        params={"code": MULTI_COMPONENT_SOURCE},
        id="Second-abc12",
        outputs=[],
    )

    component, _ = loading.instantiate_class(vertex)

    assert type(component).__name__ == "Second"
