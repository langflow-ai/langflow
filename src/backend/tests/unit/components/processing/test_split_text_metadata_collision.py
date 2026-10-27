import pytest
from lfx.components.processing.split_text import SplitTextComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


@pytest.mark.parametrize("input_type", ["json", "table"])
def test_custom_text_key_takes_precedence_over_text_metadata(input_type):
    row = {"text": "unrelated metadata", "body": "first\nsecond", "source": "example"}
    data_input = Data(data=row) if input_type == "json" else DataFrame([row])
    component = SplitTextComponent()
    component.set_attributes(
        {
            "data_inputs": data_input,
            "text_key": "body",
            "chunk_overlap": 0,
            "chunk_size": 6,
            "separator": "\n",
            "keep_separator": "False",
            "clean_output": False,
        }
    )

    result = component.split_text()

    assert result["text"].tolist() == ["first", "second"]
    assert result["source"].tolist() == ["example", "example"]
