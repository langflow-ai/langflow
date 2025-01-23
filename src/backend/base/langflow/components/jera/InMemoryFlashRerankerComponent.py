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


class InMemoryFlashRerankerComponent(Component):
    display_name = "In-Memory Flash Reranker"
    description = "An in-memory reranker that processes a query and documents to return the top N results using the specified model."
    icon = "special_components"
    name = "InMemoryFlashRerankerComponent"

    inputs = [
        MessageTextInput(name="host", display_name="Host", info="Flask API host.", required=True),
        IntInput(name="port", display_name="Port", info="Flask API port.", required=True, value=5000),
        MessageTextInput(name="query", display_name="Query", info="The query to rerank documents.", required=True),
        MessageTextInput(name="docs", display_name="Documents", info="List of documents to be reranked.", required=True),
        MessageTextInput(name="model", display_name="Model", info="The reranking model to use.", required=True, value="ms-marco-TinyBERT-L-2-v2"),
        IntInput(name="top_n", display_name="Top N", info="The number of top documents to return after reranking.", required=True, value=3),
        IntInput(name="retriever_top_n", display_name="Retriever Top N", info="The number of top documents from the retriever to consider.", required=False, value=0),
    ]

    outputs = [
        Output(display_name="Reranked Documents", name="reranked_docs", method="build_output"),
    ]

    def build_output(self) -> Data:
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        print(json.loads(self.docs))
        
        url = f"{SDCP_ROOT_URL}reranking/in_memory_flash_reranker"
        payload = {
            "query": self.query,
            "docs": json.loads(self.docs),
            "model": self.model,
            "top_n": self.top_n,
            "retriever_top_n": self.retriever_top_n,
            "callbacks": [],
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
