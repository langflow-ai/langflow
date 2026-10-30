import pytest
from lfx.components.processing.split_text import SplitTextComponent
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import HandleInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from tests.base import ComponentTestBaseWithoutClient


def _pandas_2_0_ndframe_copy(self, *, deep: bool = True):
    """``NDFrame.copy`` as implemented in pandas 2.0.x.

    Verbatim body of ``pandas/core/generic.py`` lines 6452-6454 at tag ``v2.0.3``. lfx
    declares ``pandas>=2.0.0,<3.0.0`` (src/lfx/pyproject.toml), so this is the ``copy``
    implementation ``SplitTextComponent`` runs against on the declared minimum version.
    From pandas 2.1.0 the same line reads ``self._constructor_from_mgr(...)``, which builds
    a pandas ``DataFrame`` first and therefore reaches the ``isinstance(data, pd.DataFrame)``
    branch of ``Table.__init__``.
    """
    data = self._mgr.copy(deep=deep)
    self._clear_item_cache()
    return self._constructor(data).__finalize__(self, method="copy")


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


class TestSplitTextSharedInputs(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the Split Text component under test."""
        return SplitTextComponent

    @pytest.fixture
    def default_kwargs(self):
        """Configure splitting with the content field used by a separate branch."""
        return {
            "data_inputs": Data(data={"text": "the original branch", "body": "the split branch"}),
            "text_key": "body",
            "chunk_overlap": 0,
            "chunk_size": 100,
            "separator": "\n",
            "keep_separator": "False",
            "clean_output": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Historical component versions are covered by TestSplitTextComponent."""
        return []

    @pytest.mark.parametrize("input_type", ["json", "table"])
    def test_split_text_does_not_change_the_shared_input_text_key(self, input_type):
        """Preserve the original content field on JSON and Table inputs."""
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

    def test_pandas_2_0_manager_copy_of_a_table_loses_rows(self):
        """A BlockManager handed to ``Table.__init__`` yields an empty Table.

        ``Table.__init__`` only loads ``list`` and ``dict | pd.DataFrame`` inputs, so the
        manager form pandas 2.0.x passes to ``_constructor`` falls through unset. This holds for
        both ``deep`` values, which is why switching to ``deep=True`` is not a fix.
        """
        table = DataFrame([{"text": "the original branch", "body": "the split branch"}])

        for deep in (True, False):
            copied = _pandas_2_0_ndframe_copy(table, deep=deep)
            assert len(copied) == 0
            with pytest.raises(ValueError, match="not found in Table columns"):
                copied.text_key = "body"

    def test_split_text_table_copy_survives_the_pandas_2_0_copy_path(self, monkeypatch):
        """Split Text must not depend on pandas' version-dependent ``copy()`` for its rows."""
        row = {"text": "the original branch", "body": "the split branch"}
        shared = DataFrame([row])
        monkeypatch.setattr(DataFrame, "copy", _pandas_2_0_ndframe_copy)

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

        documents = component.split_text_base()

        assert [doc.page_content for doc in documents] == ["the split branch"]
        assert shared.text_key == "text"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("producer_type", [JsonProducer, TableProducer])
    async def test_graph_fan_out_keeps_original_text_after_splitting(self, producer_type):
        """Keep shared upstream content intact after a downstream split completes."""
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

        outputs = [result async for result in graph.async_start()]

        assert outputs
        result = graph.get_vertex(observer.get_id()).built_object["value"].data
        assert result == {"original_text": "the original branch", "split_text": ["the split branch"]}
