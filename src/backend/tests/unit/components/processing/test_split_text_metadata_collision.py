import pytest
from lfx.components.processing.split_text import SplitTextComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestSplitTextMetadataCollision(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the Split Text component under test."""
        return SplitTextComponent

    @pytest.fixture
    def default_kwargs(self):
        """Configure splitting with a custom content field and conflicting metadata."""
        return {
            "data_inputs": Data(data={"text": "unrelated metadata", "body": "first\nsecond", "source": "example"}),
            "text_key": "body",
            "chunk_overlap": 0,
            "chunk_size": 6,
            "separator": "\n",
            "keep_separator": "False",
            "clean_output": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Historical component versions are covered by TestSplitTextComponent."""
        return []

    @pytest.mark.parametrize("input_type", ["json", "table"])
    def test_custom_text_key_takes_precedence_over_text_metadata(self, input_type, component_class, default_kwargs):
        """Keep generated chunks and other metadata when the text field collides."""
        if input_type == "table":
            default_kwargs["data_inputs"] = DataFrame([default_kwargs["data_inputs"].data])
        component = component_class()
        component.set_attributes(default_kwargs)

        result = component.split_text()

        assert result["text"].tolist() == ["first", "second"]
        assert result["source"].tolist() == ["example", "example"]
