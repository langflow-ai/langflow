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


class InMemoryFusionRerankerComponent(Component):
    display_name = "In-Memory Fusion Reranker"
    description = "Performs reranking on in-memory document data using a text query for relevance."
    icon = "special_components"
    name = "InMemoryFusionRerankerComponent"

    inputs = [
        MessageTextInput(name="query", display_name="Query", info="The search query for reranking.", required=True),
        MessageTextInput(
            name="docs", display_name="Documents",
            info="List of documents to rerank, as a JSON array.",
            required=True
        ),
        MessageTextInput(name="model", display_name="Model", info="The reranking model to use.", required=True),
        IntInput(name="top_n", display_name="Top N", info="Number of top results to return after reranking.",
                 required=True, value=3),
        IntInput(name="retriever_top_n", display_name="Retriever Top N",
                 info="Number of retriever results to consider.", required=False, value=0),
    ]

    outputs = [
        Output(display_name="Fusion Reranker Output", name="fusion_reranker_output", method="build_output"),
    ]

    def build_output(self) -> Data:
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN

        url = f"{SDCP_ROOT_URL}reranking/in_memory_fusion_reranker/"

        try:
            docs_list = json.loads(self.docs)
        except json.JSONDecodeError:
            return Data(
                value={
                    "status": "failed",
                    "error": "Invalid JSON provided for the 'docs' field. Ensure it is a valid JSON array.",
                }
            )

        payload = {
            "query": self.query,
            "docs": docs_list,
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
