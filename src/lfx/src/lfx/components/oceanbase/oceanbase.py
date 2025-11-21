from langchain_oceanbase.vectorstores import OceanbaseVectorStore

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import BoolInput, DropdownInput, FloatInput, HandleInput, IntInput, SecretStrInput, StrInput
from lfx.schema.data import Data


class OceanBaseVectorStoreComponent(LCVectorStoreComponent):
    display_name = "OceanBase"
    description = (
        "Oceanbase Vector Store with MySQL connection capabilities. "
        "Requires OceanBase version >= 4.3.3.0. "
        "Username format: username@tenant (e.g., root@test). "
        "Supports multiple index types: HNSW, HNSW_SQ, IVF, IVF_SQ, IVF_PQ"
    )
    name = "OceanBaseVectorStore"
    icon = "OceanBase"
    priority = 0  # Set priority to 0 to make it appear first
    recommended = True  # Mark as recommended component

    inputs = [
        StrInput(name="host", display_name="hostname", required=True, value="127.0.0.1"),
        IntInput(name="port", display_name="port", required=True, value=2881),
        StrInput(name="database", display_name="database", required=True, value="test"),
        StrInput(name="table", display_name="Table name", required=True, value="langchain_vector"),
        StrInput(name="username", display_name="The OceanBase user name.", required=True, value="root@sys"),
        SecretStrInput(name="password", display_name="The password for username.", required=True, value=""),
        DropdownInput(
            name="vidx_metric_type",
            display_name="Vector Index Metric Type",
            options=["l2", "inner_product", "cosine"],
            info="Metric method of distance between vectors.",
            value="l2",
            advanced=True,
        ),
        DropdownInput(
            name="index_type",
            display_name="Index Type",
            options=["HNSW", "HNSW_SQ", "IVF", "IVF_SQ", "IVF_PQ"],
            info="Type of vector index to use. HNSW: Hierarchical Navigable Small World graph index. "
            "IVF: Inverted File index for large-scale data. FLAT: Brute force search for small datasets.",
            value="HNSW",
            advanced=True,
        ),
        BoolInput(
            name="drop_old",
            display_name="Drop Old Table",
            info="Whether to drop the current table.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="normalize",
            display_name="Normalize Vectors",
            info="Whether to normalize vectors before storing.",
            value=False,
            advanced=True,
        ),
        StrInput(name="primary_field", display_name="Primary Field", value="id", advanced=True),
        StrInput(name="vector_field", display_name="Vector Field", value="embedding", advanced=True),
        StrInput(name="text_field", display_name="Text Field", value="document", advanced=True),
        StrInput(name="metadata_field", display_name="Metadata Field", value="metadata", advanced=True),
        StrInput(name="vidx_name", display_name="Vector Index Name", value="vidx", advanced=True),
        # HNSW parameters
        IntInput(name="M", display_name="HNSW M Parameter", value=16, advanced=True),
        IntInput(name="efConstruction", display_name="HNSW efConstruction", value=200, advanced=True),
        IntInput(name="efSearch", display_name="HNSW efSearch", value=64, advanced=True),
        # IVF parameters
        IntInput(name="nlist", display_name="IVF nlist", value=128, advanced=True),
        IntInput(name="nprobe", display_name="IVF nprobe", value=10, advanced=True),
        # IVF_PQ specific parameter
        IntInput(name="m", display_name="IVF_PQ m Parameter", value=3, advanced=True),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"], required=True),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=10,
            advanced=True,
        ),
        FloatInput(
            name="score_threshold",
            display_name="Score Threshold",
            value=0.0,
            info="Minimum relevance score for filtering results (0.0-1.0)",
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> OceanbaseVectorStore:
        try:
            import pymysql
        except ImportError as e:
            msg = "Failed to import MySQL dependencies. Install it using `uv pip install pymysql`"
            raise ImportError(msg) from e

        try:
            client = pymysql.connect(
                host=self.host, port=self.port, user=self.username, password=self.password, database=self.database
            )
            cursor = client.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            client.close()
        except Exception as e:
            msg = (
                f"Failed to connect to OceanBase: {e}. "
                "Please ensure OceanBase version >= 4.3.3.0 and connection parameters are correct."
            )
            raise ValueError(msg) from e

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        # Prepare connection arguments
        connection_args = {
            "host": self.host,
            "port": str(self.port),
            "user": self.username,
            "password": self.password,
            "db_name": self.database,
        }

        # Prepare index algorithm parameters based on index type
        vidx_algo_params = self._get_index_params()

        # Prepare additional kwargs
        kwargs = {
            "primary_field": self.primary_field,
            "vector_field": self.vector_field,
            "text_field": self.text_field,
            "metadata_field": self.metadata_field,
            "vidx_name": self.vidx_name,
        }

        if documents:
            # Extract texts and metadatas from documents for from_texts method
            texts = [doc.page_content for doc in documents]

            # Handle metadata serialization
            metadatas = []
            for doc in documents:
                # Create a deep copy of metadata to avoid modifying original data
                metadata = doc.metadata.copy()
                # Check and convert Properties objects if they exist
                for key, value in list(metadata.items()):
                    # Handle any special object types that need serialization
                    if hasattr(value, "model_dump"):
                        metadata[key] = value.model_dump()
                metadatas.append(metadata)

            oceanbase_vs = OceanbaseVectorStore.from_texts(
                texts=texts,
                embedding=self.embedding,
                metadatas=metadatas,
                table_name=self.table,
                connection_args=connection_args,
                vidx_metric_type=self.vidx_metric_type,
                vidx_algo_params=vidx_algo_params,
                drop_old=self.drop_old,
                normalize=self.normalize,
                index_type=self.index_type,
                **kwargs,
            )
        else:
            oceanbase_vs = OceanbaseVectorStore(
                embedding_function=self.embedding,
                table_name=self.table,
                connection_args=connection_args,
                vidx_metric_type=self.vidx_metric_type,
                vidx_algo_params=vidx_algo_params,
                drop_old=self.drop_old,
                normalize=self.normalize,
                index_type=self.index_type,
                **kwargs,
            )

        return oceanbase_vs

    def _get_index_params(self) -> dict:
        """Get index parameters based on the selected index type."""
        index_type = getattr(self, "index_type", "HNSW")

        if index_type in ["HNSW", "HNSW_SQ"]:
            return {
                "M": getattr(self, "M", 16),
                "efConstruction": getattr(self, "efConstruction", 200),
            }
        if index_type in ["IVF", "IVF_SQ"]:
            return {
                "nlist": getattr(self, "nlist", 128),
            }
        if index_type == "IVF_PQ":
            return {
                "nlist": getattr(self, "nlist", 128),
                "m": getattr(self, "m", 3),  # IVF_PQ requires 'm' parameter
            }
        if index_type == "FLAT":
            return {}  # FLAT index doesn't need specific parameters
        # Default to HNSW if unknown index type
        return {
            "M": getattr(self, "M", 16),
            "efConstruction": getattr(self, "efConstruction", 200),
        }

    def _get_search_params(self) -> dict:
        """Get search parameters based on the selected index type."""
        index_type = getattr(self, "index_type", "HNSW")

        if index_type in ["HNSW", "HNSW_SQ"]:
            return {"efSearch": getattr(self, "efSearch", 64)}
        if index_type in ["IVF", "IVF_SQ", "IVF_PQ"]:
            return {"nprobe": getattr(self, "nprobe", 10)}
        if index_type == "FLAT":
            return {}  # FLAT index doesn't need specific search parameters
        # Default to HNSW if unknown index type
        return {"efSearch": getattr(self, "efSearch", 64)}

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            # Prepare search parameters based on index type
            search_params = self._get_search_params()

            # Parse and validate score_threshold
            try:
                score_threshold = (
                    float(self.score_threshold) if self.score_threshold and str(self.score_threshold).strip() else None
                )
            except (ValueError, TypeError):
                score_threshold = None

            # Build search_kwargs by merging number_of_results with search_params
            search_kwargs = {"k": self.number_of_results, **search_params}

            # Use public as_retriever API with score_threshold if provided
            if score_threshold is not None:
                retriever = vector_store.as_retriever(
                    search_type="similarity_score_threshold",
                    search_kwargs={"score_threshold": score_threshold, **search_kwargs},
                )
            else:
                retriever = vector_store.as_retriever(search_kwargs=search_kwargs)

            docs = retriever.invoke(self.search_query)
            data = docs_to_data(docs)
            self.status = data
            return data
        return []
