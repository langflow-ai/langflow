from langflow.custom import Component
from langflow.io import MessageTextInput, IntInput, Output
from langflow.schema import Data
import json
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class DataStoreFlashRerankerComponent(Component):
    display_name = "Data Store Flash Reranker Component"
    description = (
        "Performs flash reranking on a datastore using a text query for relevance."
    )
    icon = "special_components"
    name = "DataStoreFlashRerankerComponent"

    inputs = [
        MessageTextInput(name="host", display_name="Host", info="Milvus server host.", required=True),
        IntInput(name="port", display_name="Port", info="Milvus server port.", required=True, value=0),
        MessageTextInput(name="user", display_name="User", info="Database user credentials.", required=True),
        MessageTextInput(name="password", display_name="Password", info="User password.", required=True),
        MessageTextInput(name="db_name", display_name="Db Name", info="Database name.", required=False),
        MessageTextInput(name="collection_name", display_name="Collection Name", info="Target collection for reranking.", required=True),
        MessageTextInput(name="query", display_name="Query", info="The query to rerank documents.", required=True),
        MessageTextInput(name="model", display_name="Model", info="The reranking model to use.", required=True),
        IntInput(name="top_n", display_name="Top N", info="The number of top documents to return after reranking.", required=True, value=3),
        MessageTextInput(name="embedding_model_name", display_name="Embedding Model Name", info="Embedding model name.", required=False),
        MessageTextInput(name="primary_field", display_name="Primary Field", info="Primary field in the collection.", required=False),
        MessageTextInput(name="text_field", display_name="Text Field", info="Text field in the collection.", required=False),
        MessageTextInput(name="vector_field", display_name="Vector Field", info="Vector field in the collection.", required=False),
        MessageTextInput(name="search_params", display_name="Search Params", info="Search parameters for Milvus vector retrieval in JSON format.", required=False),
    ]

    outputs = [
        Output(display_name="Reranked Documents", name="reranked_docs", method="build_output"),
    ]

    def build_output(self) -> Data:
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

        url = f"{SDCP_ROOT_URL}reranking/data_store_flash_reranker/"

        payload = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "db_name": self.db_name,
            "collection_name": self.collection_name,
            "query": self.query,
            "model": self.model,
            "top_n": self.top_n,
            "embedding_model_name": self.embedding_model_name,
            "primary_field": self.primary_field,
            "text_field": self.text_field,
            "vector_field": self.vector_field,
            "search_params": json.loads(self.search_params) if self.search_params else {},  
        }

        try:
            response = http.request("POST", url, headers=headers, body=json.dumps(payload))
            if response.status == 200:
                result = json.loads(response.data.decode("utf-8"))
                return Data(value={"status": "ok", "data": result})
            else:
                return Data(
                    value={
                        "status": "failed",
                        "error": f"HTTP {response.status}: {response.data.decode('utf-8')}",
                    }
                )
        except Exception as e:
            return Data(value={"status": "failed", "error": str(e)})
