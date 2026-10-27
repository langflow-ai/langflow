import pytest
from lfx.components.processing.split_text import SplitTextComponent
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import HandleInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


@pytest.mark.parametrize("input_type", ["json", "table"])
def test_split_text_does_not_change_the_shared_input_text_key(input_type):
    row = {"text": "the original branch", "body": "the split branch"}
    shared = Data(data=row) if input_type == "json" else DataFrame([row])
    component = SplitTextComponent()
    component.set_attributes(
        {
            "data_inputs": shared,
            "text_key": "body",
            "chunk_overlap": 0,
            "chunk_size": 100,
            "separator": "\n",
            "keep_separator": "False",
            "clean_output": True,
        }
    )

    result = component.split_text()

    assert result["text"].tolist() == ["the split branch"]
    assert shared.text_key == "text"
    if input_type == "json":
        assert shared.get_text() == "the original branch"
    else:
        assert shared.to_lc_documents()[0].page_content == "the original branch"


class JsonProducer(Component):
    outputs = [Output(name="value", method="produce")]

    def produce(self) -> Data:
        return Data(data={"text": "the original branch", "body": "the split branch"})


class TableProducer(Component):
    outputs = [Output(name="value", method="produce")]

    def produce(self) -> DataFrame:
        return DataFrame([{"text": "the original branch", "body": "the split branch"}])


class ObserveShared(Component):
    inputs = [
        HandleInput(name="original", input_types=["Data", "JSON", "DataFrame", "Table"]),
        HandleInput(name="after_split", input_types=["DataFrame", "Table"]),
    ]
    outputs = [Output(name="value", method="observe")]

    def observe(self) -> Data:
        original = self.original
        content = original.get_text() if isinstance(original, Data) else original.to_lc_documents()[0].page_content
        return Data(data={"original_text": content, "split_text": self.after_split["text"].tolist()})


@pytest.mark.asyncio
@pytest.mark.parametrize("producer_type", [JsonProducer, TableProducer])
async def test_graph_fan_out_keeps_original_text_after_splitting(producer_type):
    producer = producer_type(_id="producer")
    splitter = SplitTextComponent(_id="splitter").set(
        data_inputs=producer.produce,
        text_key="body",
        chunk_overlap=0,
        chunk_size=100,
        separator="\n",
        keep_separator="False",
        clean_output=True,
    )
    observer = ObserveShared(_id="observer").set(original=producer.produce, after_split=splitter.split_text)
    graph = Graph(producer, observer)

    outputs = await graph.arun(inputs=[{}], outputs=[observer.get_id()])

    result = outputs[0].outputs[0].outputs["value"]["message"]
    assert result == {"original_text": "the original branch", "split_text": ["the split branch"]}
