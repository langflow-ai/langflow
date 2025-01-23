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


class DataStoreFusionRerankerComponent(Component):
    display_name = "Data Store Fusion Reranker"
    description = (
        "A reranker that combines data store search results with reranking for optimal relevance."
    )
    icon = "special_components"
    name = "DataStoreFusionRerankerComponent"

    inputs = [
        MessageTextInput(name="host", display_name="Host", info="Database server host.", required=True),
        IntInput(name="port", display_name="Port", info="Database server port.", required=True, value=0),
        MessageTextInput(name="user", display_name="User", info="Database user credentials.", required=True),
        MessageTextInput(name="password", display_name="Password", info="User password.", required=True),
        MessageTextInput(name="db_name", display_name="Database Name", info="The database name.", required=True),
        MessageTextInput(name="collection_name", display_name="Collection Name", info="The target collection name.", required=True),
        MessageTextInput(name="query", display_name="Query", info="The search query for the reranker.", required=True),
        MessageTextInput(name="model", display_name="Model", info="The reranking model to use.", required=True),
        IntInput(name="top_n", display_name="Top N", info="Number of top results to return after reranking.", required=True, value=3),
        MessageTextInput(name="embedding_model_name", display_name="Embedding Model Name", info="Name of the embedding model.", required=True),
        MessageTextInput(name="primary_field", display_name="Primary Field", info="The primary field for identification.", required=True),
        MessageTextInput(name="text_field", display_name="Text Field", info="The field containing text data.", required=True),
        MessageTextInput(name="vector_field", display_name="Vector Field", info="The field containing vector data.", required=True),
        MessageTextInput(name="search_params", display_name="Search Params", info="Additional search parameters.", required=False, value="{}"),
    ]

    outputs = [
        Output(display_name="Fusion Reranker Output", name="fusion_reranker_output", method="build_output"),
    ]

    def build_output(self) -> Data:
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

        url = f"{SDCP_ROOT_URL}reranking/data_store_fusion_reranker"

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
