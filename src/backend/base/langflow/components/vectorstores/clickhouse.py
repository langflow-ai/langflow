from langchain_community.vectorstores import Clickhouse, ClickhouseSettings

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.inputs.inputs import BoolInput, FloatInput
from langflow.io import (
    DictInput,
    DropdownInput,
    HandleInput,
    IntInput,
    SecretStrInput,
    StrInput,
)
from langflow.schema.data import Data


class ClickhouseVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Clickhouse"
    description = "Clickhouse Vector Store with search capabilities"
    name = "Clickhouse"
    icon = "Clickhouse"

    inputs = [
        StrInput(name="host", display_name="hostname", required=True, value="localhost"),
        IntInput(name="port", display_name="port", required=True, value=8123),
        StrInput(name="database", display_name="database", required=True),
        StrInput(name="table", display_name="Table name", required=True),
        StrInput(name="username", display_name="The ClickHouse user name.", required=True),
        SecretStrInput(name="password", display_name="The password for username.", required=True),
        DropdownInput(
            name="index_type",
            display_name="index_type",
            options=["annoy", "vector_similarity"],
            info="Type of the index.",
            value="annoy",
            advanced=True,
        ),
        DropdownInput(
            name="metric",
            display_name="metric",
            options=["angular", "euclidean", "manhattan", "hamming", "dot"],
            info="Metric to compute distance.",
            value="angular",
            advanced=True,
        ),
        BoolInput(
            name="secure",
            display_name="Use https/TLS. This overrides inferred values from the interface or port arguments.",
            value=False,
            advanced=True,
        ),
        StrInput(name="index_param", display_name="Param of the index", value="100,'L2Distance'", advanced=True),
        DictInput(name="index_query_params", display_name="index query params", advanced=True),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
        FloatInput(name="score_threshold", display_name="Score threshold", advanced=True),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> Clickhouse:
        try:
            import clickhouse_connect
        except ImportError as e:
            msg = (
                "Failed to import Clickhouse dependencies. "
                "Install it using `pip install langflow[clickhouse-connect] --pre`"
            )
            raise ImportError(msg) from e

        try:
            client = clickhouse_connect.get_client(
                host=self.host, port=self.port, username=self.username, password=self.password
            )
            client.command("SELECT 1")
        except Exception as e:
            msg = f"Failed to connect to Clickhouse: {e}"
            raise ValueError(msg) from e

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        kwargs = {}
        if self.index_param:
            kwargs["index_param"] = self.index_param.split(",")
        if self.index_query_params:
            kwargs["index_query_params"] = self.index_query_params

        settings = ClickhouseSettings(
            table=self.table,
            database=self.database,
            host=self.host,
            index_type=self.index_type,
            metric=self.metric,
            password=self.password,
            port=self.port,
            secure=self.secure,
            username=self.username,
            **kwargs,
        )
        if documents:
            clickhouse_vs = Clickhouse.from_documents(documents=documents, embedding=self.embedding, config=settings)

        else:
            clickhouse_vs = Clickhouse(embedding=self.embedding, config=settings)

        return clickhouse_vs

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            kwargs = {}
            if self.score_threshold:
                kwargs["score_threshold"] = self.score_threshold

            docs = vector_store.similarity_search(query=self.search_query, k=self.number_of_results, **kwargs)

            data = docs_to_data(docs)
            self.status = data
            return data
        return []
