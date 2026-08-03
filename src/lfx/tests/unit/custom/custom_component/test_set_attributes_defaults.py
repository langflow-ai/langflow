import pytest
from lfx.custom.custom_component.component import Component
from lfx.graph.graph.base import Graph
from lfx.inputs.inputs import BoolInput, FloatInput, IntInput, MessageTextInput, StrInput
from lfx.schema.data import Data
from lfx.template import Output

PROBE_CODE = """
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, IntInput, MessageTextInput
from lfx.schema.data import Data
from lfx.template import Output


class DefaultsProbe(Component):
    display_name = "Defaults Probe"
    name = "DefaultsProbe"

    inputs = [
        MessageTextInput(name="config_name", display_name="Config name", value="", required=False),
        IntInput(name="retries", display_name="Retries", value=0, required=False),
        BoolInput(name="dry_run", display_name="Dry run", value=False, required=False),
        MessageTextInput(name="kept", display_name="Kept", value="keep-me", required=False),
    ]
    outputs = [Output(display_name="Seen", name="seen", method="build")]

    def build(self) -> Data:
        return Data(
            data={
                "config_name": self.config_name,
                "retries": self.retries,
                "dry_run": self.dry_run,
                "kept": self.kept,
            }
        )
"""


class FalsyDefaultsComponent(Component):
    display_name = "Falsy Defaults"
    name = "FalsyDefaultsComponent"

    inputs = [
        StrInput(name="empty_str", display_name="Empty str", value=""),
        MessageTextInput(name="empty_message_text", display_name="Empty message text", value=""),
        StrInput(name="filled_str", display_name="Filled str", value="keep-me"),
        IntInput(name="zero_int", display_name="Zero int", value=0),
        IntInput(name="nonzero_int", display_name="Nonzero int", value=7),
        FloatInput(name="zero_float", display_name="Zero float", value=0.0),
        BoolInput(name="false_bool", display_name="False bool", value=False),
        BoolInput(name="true_bool", display_name="True bool", value=True),
    ]
    outputs = [Output(display_name="Out", name="out", method="build")]

    def build(self) -> Data:
        return Data(data={})


@pytest.mark.parametrize(
    ("field_name", "expected"),
    [
        ("empty_str", ""),
        ("empty_message_text", ""),
        ("filled_str", "keep-me"),
        ("zero_int", 0),
        ("nonzero_int", 7),
        ("zero_float", 0.0),
        ("false_bool", False),
        ("true_bool", True),
    ],
)
def test_should_keep_declared_default_when_field_missing_from_params(field_name, expected):
    component = FalsyDefaultsComponent()
    component.map_inputs(FalsyDefaultsComponent.inputs)

    component.set_attributes({})

    value = getattr(component, field_name)
    assert value == expected
    assert type(value) is type(expected)


def test_should_not_override_supplied_param_with_declared_default():
    component = FalsyDefaultsComponent()
    component.map_inputs(FalsyDefaultsComponent.inputs)

    component.set_attributes({"empty_str": "from-params", "zero_int": 42})

    assert component.empty_str == "from-params"
    assert component.zero_int == 42
    assert component.false_bool is False


async def test_should_keep_falsy_defaults_when_stored_template_omits_fields():
    """A saved flow whose template predates an input must still get the declared default."""
    node = FalsyDefaultsComponent().to_frontend_node()
    node["data"]["node"]["template"]["code"]["value"] = PROBE_CODE
    node["data"]["type"] = "DefaultsProbe"

    template = node["data"]["node"]["template"]
    for field_name in list(template):
        if field_name not in {"code", "_type"}:
            template.pop(field_name)
    node["data"]["node"]["outputs"] = [{"name": "seen", "display_name": "Seen", "method": "build", "types": ["Data"]}]

    node_id = node["id"]
    graph = Graph.from_payload({"nodes": [node], "edges": []}, flow_id="le2095", flow_name="le2095")
    graph.session_id = "le2095"
    async for _ in graph.async_start():
        pass

    seen = graph.get_vertex(node_id).built_object["seen"].data
    assert seen["config_name"] == ""
    assert seen["retries"] == 0
    assert seen["dry_run"] is False
    assert seen["kept"] == "keep-me"
