import pytest
from lfx.components.processing.filter_data_values import DataFilterComponent
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import Output
from lfx.schema import Data
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


def _rows() -> list[Data]:
    return [Data(data={"route": "CMIP"}), Data(data={"route": "OTHER"})]


def _upstream(text: object) -> Component:
    """Return an upstream component whose Data output carries ``text``, as a saved flow would."""

    class _Emit(Component):
        display_name = "Emit Data"
        name = "EmitData"
        outputs = [Output(display_name="Data", name="data", method="emit")]

        def emit(self) -> Data:
            return Data(data={"text": text})

    return _Emit(_id="emit")


class TestDataFilterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return DataFilterComponent

    @pytest.fixture
    def default_kwargs(self):
        # Only input_data: filter_key and filter_value keep their defaults ("route" / "CMIP").
        return {"input_data": _rows()}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_defaults_filter_plain_text(self):
        component = DataFilterComponent().set(input_data=_rows())

        assert [item.data for item in component.filter_data()] == [{"route": "CMIP"}]

    @pytest.mark.parametrize(
        ("operator", "value", "expected"),
        [
            ("equals", "CMIP", ["CMIP"]),
            ("not equals", "CMIP", ["OTHER"]),
            ("contains", "MI", ["CMIP"]),
            ("starts with", "CM", ["CMIP"]),
            ("ends with", "IP", ["CMIP"]),
        ],
    )
    def test_operators_with_text_inputs(self, operator, value, expected):
        component = DataFilterComponent().set(
            input_data=_rows(), filter_key="route", filter_value=value, operator=operator
        )

        assert [item.data["route"] for item in component.filter_data()] == expected

    @pytest.mark.parametrize(
        ("text", "operator", "expected"),
        [("CMIP", "equals", ["CMIP"]), (123, "equals", [123]), (12, "contains", [123])],
        ids=["str", "int-equals", "int-contains"],
    )
    async def test_graph_data_edge_into_filter_value(self, text, operator, expected):
        # In a graph run, input validation unwraps the connected Data to its text value,
        # which keeps its type (a number stays a number).
        upstream = _upstream(text)
        component = DataFilterComponent(_id="filter")
        component.set(
            input_data=[*_rows(), Data(data={"route": 123})],
            filter_key="route",
            filter_value=upstream.emit,
            operator=operator,
        )
        graph = Graph(upstream, component)

        async for _ in graph.async_start():
            pass

        filtered = graph.get_vertex("filter").results["filtered_data"]
        assert [item.data["route"] for item in filtered] == expected

    @pytest.mark.parametrize(
        ("filter_key", "filter_value"),
        [
            (Message(text="route"), Message(text="CMIP")),
            (Data(data={"text": "route"}), Data(data={"text": "CMIP"})),
            (Data(data={"field": "route"}, text_key="field"), "CMIP"),
        ],
        ids=["message", "data", "data-custom-text-key"],
    )
    def test_sdk_objects_use_their_text(self, filter_key, filter_value):
        component = DataFilterComponent().set(input_data=_rows(), filter_key=filter_key, filter_value=filter_value)

        assert [item.data for item in component.filter_data()] == [{"route": "CMIP"}]

    def test_empty_input_returns_empty_list(self):
        component = DataFilterComponent().set(input_data=[], filter_key="route", filter_value="CMIP")

        assert component.filter_data() == []
        assert component.status == "Input data is empty."

    @pytest.mark.parametrize(
        ("filter_key", "filter_value"),
        [("", "CMIP"), ("route", ""), ("route", Data(data={"text": None}))],
        ids=["empty-key", "empty-value", "none-text"],
    )
    def test_missing_filter_returns_input_unchanged(self, filter_key, filter_value):
        rows = _rows()
        component = DataFilterComponent().set(input_data=rows, filter_key=filter_key, filter_value=filter_value)

        assert component.filter_data() == rows
        assert component.status == "Filter key or value is missing."
