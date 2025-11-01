from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document
from langchain_db2.db2vs import DB2VS

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.inputs.inputs import DictInput, FloatInput
from lfx.io import (
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
)
from lfx.schema.data import Data
from lfx.serialization import serialize


class DB2VectorStoreComponent(LCVectorStoreComponent):
    display_name = "Db2"
    description = "Db2 Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/db2/"
    name = "Db2"
    icon = "Db2"

    inputs = [
        MessageTextInput(
            name="database_name", display_name="Db2 database name", info="Db2 database name for connection"
        ),
        MessageTextInput(name="username", display_name="Username", info="Username for the Db2 database."),
        SecretStrInput(name="password", display_name="Password", info="User password for the Db2 database."),
        # e.g. conn_str=f"DATABASE={DB_NAME};hostname={DB_HOST};port={DB_PORT};uid={DB_USER};pwd={DB_PASSWORD};"
        MessageTextInput(
            name="conn_str",
            display_name="Connect String",
            info="The string that contains detailed connection arguments. "
            "If it is specified, no info in database_name/username/password field will be used",
        ),
        MessageTextInput(
            name="table_name",
            display_name="Table Name",
            info="The name of the table where vectors will be stored in Db2 database instance.",
            required=True,
        ),
        DropdownInput(
            name="distance_strategy",
            display_name="Distance Strategy",
            info="Configure the distance strategy for the vector store",
            options=["DOT_PRODUCT", "COSINE", "EUCLIDEAN_DISTANCE"],
            required=True,
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            info="Search type to use",
            options=["Similarity", "Similarity with score", "Max Marginal Relevance Search"],
            value="Similarity",
            advanced=True,
        ),
        DictInput(
            name="search_filter",
            display_name="Search Metadata Filter",
            info="Optional dictionary of filters to apply to the search query.",
            advanced=True,
            list=True,
        ),
        FloatInput(
            name="lambda_mult",
            display_name="lambda_mult for Max Marginal Relevance Search",
            info="the degree of diversity among the results with 0 corresponding "
            "to maximum diversity and 1 to minimum diversity",
            value=0.5,
            advanced=True,
        ),
        IntInput(
            name="fetch_k",
            display_name="fetch_k for Max Marginal Relevance Search",
            info="Number of Documents to fetch before filtering to pass to MMR algorithm.",
            value=20,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> DB2VS:
        try:
            import ibm_db_dbi
        except ImportError as e:
            msg = "Please install ibm_db package to use `pip install ibm_db`"
            raise ImportError(msg) from e

        database_name = self.database_name
        username = self.username
        password = self.password
        conn_str = self.conn_str

        if conn_str:
            self.client = ibm_db_dbi.connect(conn_str, "", "")
        else:
            self.client = ibm_db_dbi.connect(database_name, username, password)

        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        documents = [
            Document(page_content=doc.page_content, metadata=serialize(doc.metadata, to_str=True)) for doc in documents
        ]

        if not self.embedding:
            msg = "Embedding model is required to create a vector store."
            raise ValueError(msg)

        distance_strategy = DistanceStrategy[self.distance_strategy]
        if documents:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            vs = DB2VS.from_documents(
                documents,
                self.embedding,
                client=self.client,
                table_name=self.table_name,
                distance_strategy=distance_strategy,
            )
        else:
            self.log("No documents to initialize the Vector Store.")
            vs = DB2VS(
                self.embedding, client=self.client, table_name=self.table_name, distance_strategy=distance_strategy
            )
        self.client.commit()
        return vs

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        self.log(f"Search input: {self.search_query}")
        self.log(f"Search type: {self.search_type}")
        self.log(f"Number of results: {self.number_of_results}")
        self.log(f"Filter: {self.search_filter}")

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            try:
                if self.search_type == "Similarity with score":
                    docs_with_scores = vector_store.similarity_search_with_score(
                        query=self.search_query, k=self.number_of_results, filter=self.search_filter
                    )
                    # Add scores to document metadata
                    docs = []
                    for doc, score in docs_with_scores:
                        doc.metadata["similarity_score"] = score
                        docs.append(doc)
                elif self.search_type == "Max Marginal Relevance Search":
                    docs = vector_store.max_marginal_relevance_search(
                        query=self.search_query,
                        k=self.number_of_results,
                        fetch_k=self.fetch_k,
                        lambda_mult=self.lambda_mult,
                        filter=self.search_filter,
                    )
                else:
                    docs = vector_store.similarity_search(
                        query=self.search_query, k=self.number_of_results, filter=self.search_filter
                    )
            except KeyError as e:
                if "content" in str(e):
                    msg = (
                        "You should ingest data through Langflow (or LangChain) to query it in Langflow. "
                        "Your collection does not contain a field name 'content'."
                    )
                    raise ValueError(msg) from e
                raise

            self.log(f"Retrieved documents: {len(docs)}")

            data = docs_to_data(docs)
            self.status = data
            return data
        return []
