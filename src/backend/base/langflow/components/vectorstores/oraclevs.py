from langchain_community.vectorstores import OracleVS
from langchain_community.vectorstores.utils import DistanceStrategy

from langflow.base.vectorstores.model import (
    LCVectorStoreComponent,
    check_cached_vector_store,
)
from langflow.helpers.data import docs_to_data
from langflow.io import HandleInput, IntInput, SecretStrInput, StrInput
from langflow.schema import Data


class OracleVectorStoreComponent(LCVectorStoreComponent):
    display_name = "OracleVS"
    description = "Oracle Vector Store with search capabilities"
    name = "oraclevs"
    icon = "cpu"

    inputs = [
        StrInput(
            name="dsn",
            display_name="DSN",
            required=True,
            info="The dsn value can be one of Oracle Database's naming methods:"
            "An Oracle Easy Connect string, e.g. dbhost:port/service_name"
            "A Connect Descriptor"
            "A TNS Alias mapping to a Connect Descriptor stored in a tnsnames.ora file"
            "Refer https://python-oracledb.readthedocs.io/en/latest/user_guide/connection_handling.html for details",
        ),
        StrInput(
            name="user",
            display_name="Database User",
            required=True,
        ),
        SecretStrInput(
            name="password",
            display_name="User Password",
            required=True,
        ),
        StrInput(
            name="collection_name",
            display_name="Table",
            required=True,
        ),
        StrInput(
            name="distance_strategy",
            display_name="Distance Strategy",
            value="COSINE",
            required=False,
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
            required=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    @classmethod
    def _get_distance_strategy(cls, distance_strategy) -> DistanceStrategy:
        distance_strategy_map = {
            "EUCLIDEAN": DistanceStrategy.EUCLIDEAN_DISTANCE,
            "DOT": DistanceStrategy.DOT_PRODUCT,
            "COSINE": DistanceStrategy.COSINE,
        }

        # Attempt to return the corresponding DistanceStrategy
        if distance_strategy in distance_strategy_map:
            return distance_strategy_map[distance_strategy]

        # If it's an unsupported distance strategy, raise an error
        err_msg = f"Unsupported distance strategy: {distance_strategy}"
        raise ValueError(err_msg)

    @check_cached_vector_store
    def build_vector_store(self, client) -> OracleVS:
        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            oraclevs = OracleVS.from_documents(
                documents=documents,
                embedding=self.embedding,
                client=client,
                table_name=self.collection_name,
                distance_strategy=self._get_distance_strategy(self.distance_strategy),
            )
        else:
            oraclevs = OracleVS(
                client=client,
                table_name=self.collection_name,
                embedding_function=self.embedding,
                distance_strategy=self._get_distance_strategy(self.distance_strategy),
            )

        return oraclevs

    def search_documents(self) -> list[Data]:
        try:
            import oracledb
        except ImportError as e:
            msg = "oracledb is not installed. Please install it with `pip install oracledb`."
            raise ImportError(msg) from e

        with oracledb.connect(user=self.user, password=self.password, dsn=self.dsn) as connection:
            vector_store: OracleVS = self.build_vector_store(client=connection)

            if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
                docs = vector_store.similarity_search(
                    query=self.search_query,
                    k=self.number_of_results,
                )

                data = docs_to_data(docs)
                self.status = data
                return data
        return []
