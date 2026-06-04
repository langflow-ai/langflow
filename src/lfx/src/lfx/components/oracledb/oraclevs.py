import hashlib
import json
from contextlib import suppress
from decimal import Decimal
from importlib.metadata import version
from typing import Any

import oracledb
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_oracledb.vectorstores import OracleVS
from langchain_oracledb.vectorstores.oraclevs import create_index
from pydantic import BaseModel

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import BoolInput, DictInput, DropdownInput, HandleInput, IntInput, SecretStrInput, StrInput
from lfx.schema.data import Data

from .connection import build_connection_params


def serialize(obj: Any) -> dict | list:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize(item) for item in obj]
    if isinstance(obj, tuple):
        return [serialize(item) for item in obj]
    return obj


def normalize_search_result(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {key: normalize_search_result(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [normalize_search_result(item) for item in obj]
    if isinstance(obj, tuple):
        return [normalize_search_result(item) for item in obj]
    return obj


class OracleVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Oracle Vector Store"
    description = "Oracle vector store with search capabilities"
    name = "OracleVS"
    icon = "Oracle"

    inputs = [
        SecretStrInput(name="user", display_name="User", required=False),
        SecretStrInput(name="password", display_name="Password", required=False),
        SecretStrInput(name="dsn", display_name="DSN", required=True),
        SecretStrInput(name="wallet_password", display_name="Wallet Password", required=False, advanced=True),
        DictInput(
            name="connection_params",
            display_name="Additional Connection Parameters",
            info="Non-secret arguments passed to python-oracledb connect(), such as config_dir and wallet_location.",
            list=True,
            required=False,
            advanced=True,
        ),
        StrInput(name="table_name", display_name="Table Name", required=True),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"], required=True),
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
            options=["Similarity", "MMR (Max Marginal Relevance)"],
            value="Similarity",
            advanced=True,
        ),
        DropdownInput(
            name="distance_strategy",
            display_name="Distance Strategy",
            options=["EUCLIDEAN", "DOT", "COSINE"],
            value="COSINE",
            advanced=True,
        ),
        BoolInput(
            name="create_index",
            display_name="Create Vector Index",
            info=(
                "Boolean flag to determine whether to create a vector index. "
                "Check `Controls` to use advanced parameters."
            ),
            value=True,
        ),
        DictInput(
            name="index_params",
            display_name="Vector Index Parameters",
            list=True,
            advanced=True,
        ),
        BoolInput(
            name="mutate_on_duplicate",
            display_name="Mutate on Duplicate Inserts",
            info="Whether to update existing rows when duplicate inserts are encountered.",
            value=False,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> OracleVS:
        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            inp = _input
            if isinstance(_input, Data):
                inp = _input.to_lc_document()

            if hasattr(inp, "metadata"):
                inp.metadata = serialize(inp.metadata)

            documents.append(inp)

        opened_connection = False
        if (not hasattr(self, "connection")) or (not self.connection):
            connection_params = build_connection_params(
                self.connection_params,
                user=self.user,
                password=self.password,
                dsn=self.dsn,
                wallet_password=self.wallet_password,
            )
            self.connection = oracledb.connect(**connection_params)
            opened_connection = True

        distance_strategy2function = {
            "EUCLIDEAN": DistanceStrategy.EUCLIDEAN_DISTANCE,
            "DOT": DistanceStrategy.DOT_PRODUCT,
            "COSINE": DistanceStrategy.COSINE,
        }
        distance_strategy = distance_strategy2function[self.distance_strategy]

        params = {
            "client": self.connection,
            "table_name": self.table_name,
            "distance_strategy": distance_strategy,
        }

        if not version("langchain_oracledb").startswith("1.0"):
            params["mutate_on_duplicate"] = self.mutate_on_duplicate

        try:
            if documents:
                vs = OracleVS.from_documents(embedding=self.embedding, documents=documents, **params)
            else:
                vs = OracleVS(embedding_function=self.embedding, **params)

            if self.create_index:
                index_params = (self.index_params or {}).copy()

                if "idx_name" not in index_params:
                    params_str = json.dumps(index_params, sort_keys=True)
                    distance_strategy = self.distance_strategy
                    params_str = params_str + distance_strategy
                    index_name = params["table_name"] + "_idx_" + hashlib.sha256(params_str.encode()).hexdigest()[:16]
                    index_params["idx_name"] = index_name

                if "idx_type" not in index_params:
                    index_params["idx_type"] = "HNSW"

                if "" in index_params:
                    del index_params[""]
                create_index(self.connection, vs, index_params)
        except Exception:
            if opened_connection:
                with suppress(Exception):
                    self.connection.close()
                self.connection = None
            raise

        return vs

    def _map_search_type(self) -> str:
        if self.search_type == "MMR (Max Marginal Relevance)":
            return "mmr"
        return "similarity"

    def _build_search_args(self) -> dict[str, Any]:
        return {"k": self.number_of_results}

    def search_documents(self) -> list[Data]:
        raw_search_query = getattr(self, "search_query", None)
        search_query = str(raw_search_query).strip() if raw_search_query is not None else ""

        if not search_query:
            self.status = []
            return []

        vector_store = self.build_vector_store()
        docs = vector_store.search(
            query=search_query,
            search_type=self._map_search_type(),
            **self._build_search_args(),
        )

        data = docs_to_data(docs)
        for item in data:
            item.data = normalize_search_result(item.data)
        self.status = data
        return data
