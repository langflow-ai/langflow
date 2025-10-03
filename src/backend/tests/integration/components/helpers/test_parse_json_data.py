from lfx.components.input_output import ChatInput
from lfx.components.processing.parse_json_data import ParseJSONDataComponent
from lfx.schema import Data

from tests.integration.components.mock_components import TextToData
from tests.integration.utils import ComponentInputHandle, pyleak_marker, run_single_component

pytestmark = pyleak_marker()


async def test_from_data():
    outputs = await run_single_component(
        ParseJSONDataComponent,
        inputs={
            "input_value": ComponentInputHandle(
                clazz=TextToData, inputs={"text_data": ['{"key":"value1"}'], "is_json": True}, output_name="from_text"
            ),
            "query": ".[0].key",
        },
    )
    assert outputs["filtered_data"] == [Data(text="value1")]

    outputs = await run_single_component(
        ParseJSONDataComponent,
        inputs={
            "input_value": ComponentInputHandle(
                clazz=TextToData,
                inputs={"text_data": ['{"key":[{"field1": 1, "field2": 2}]}'], "is_json": True},
                output_name="from_text",
            ),
            "query": ".[0].key.[0].field2",
        },
    )
    assert outputs["filtered_data"] == [Data(text="2")]


async def test_from_message():
    outputs = await run_single_component(
        ParseJSONDataComponent,
        inputs={
            "input_value": ComponentInputHandle(clazz=ChatInput, inputs={}, output_name="message"),
            "query": ".key",
        },
        run_input="{'key':'value1'}",
    )
    assert outputs["filtered_data"] == [Data(text="value1")]

    outputs = await run_single_component(
        ParseJSONDataComponent,
        inputs={
            "input_value": ComponentInputHandle(clazz=ChatInput, inputs={}, output_name="message"),
            "query": ".key.[0].field2",
        },
        run_input='{"key":[{"field1": 1, "field2": 2}]}',
    )
    assert outputs["filtered_data"] == [Data(text="2")]
