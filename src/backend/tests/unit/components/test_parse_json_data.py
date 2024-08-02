import pytest

from langflow.components.helpers.ParseJSONData import ParseJSONDataComponent
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.services.database.models.api_key import ApiKeyCreate



def test_parse_json():
    component = ParseJSONDataComponent()
    component.input_value = Data(data={"key": "value1"})
    component.query = ".[0].key"
    assert [Data(text="value1")] == component.filter_data()

    component.input_value = [Data(data={"key": "value1"})]
    component.query = ".[0].key"

    assert [Data(text="value1")] == component.filter_data()

    component.input_value = "{\"key\": \"value1\"}"
    component.query = ".[0].key"

    assert [Data(text="value1")] == component.filter_data()

    component.input_value = ["{\"key\": \"value1\"}"]
    component.query = ".[0].key"

    assert [Data(text="value1")] == component.filter_data()

    component.input_value = Message(text="{\"key\": \"value1\"}")
    component.query = ".[0].key"
    assert [Data(text="value1")] == component.filter_data()

    component.input_value = [Message(text="{\"key\": \"value1\"}")]
    component.query = ".[0].key"
    assert [Data(text="value1")] == component.filter_data()
