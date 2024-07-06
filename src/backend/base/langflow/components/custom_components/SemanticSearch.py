import json
import os
import time

from langchain.agents import Tool

from langflow.custom import CustomComponent
from langflow.schema import Data
from langflow.schema.message import Message

from cognite.client import CogniteClient, ClientConfig
from cognite.client.credentials import OAuthClientCredentials


class SemanticSearch(CustomComponent):
    display_name = "Semantic Search"
    description = "Cognite Semantic Search"

    def build_config(self) -> dict:
        return {
            "file_ids": {"display_name": "File IDs", "description": "Comma-separated list of internal file ids (integers)"}
        }

    def build(self, file_ids: str) -> Tool:
        def semantic_search(question: str) -> str:
            """
            Search for answers in documents
            """
            print(f"TOOL: semantic_search({question}, {file_ids})")
            body = self._create_request_body(question, file_ids)
            response = self._request_with_retry(body)
            response_json = response.json()
            #print(json.dumps(response_json, indent=2))
            return json.dumps(response_json, indent=2)

        return Tool(
            name="semantic_search",
            description="Search for answers in documents",
            func=semantic_search,
        )

    def _create_request_body(self, question: str, file_ids: str):
        file_ids_list = [int(file_id) for file_id in file_ids.split(",")]
        body = {
            "filter": {
                "and": [
                    {"semanticSearch": {"property": ["content"], "value": question}},
                    {"in": {"property": ["id"], "values": file_ids_list}},
                ]
            },
            "limit": 1,
        }
        return body

    def _request_with_retry(self, body):
        project = os.environ["COGNITE_PROJECT"]
        client = CogniteClient(
            config=ClientConfig(
                client_name=__file__,
                project=project,
                base_url=os.environ["COGNITE_BASE_URL"],
                credentials=OAuthClientCredentials(
                    token_url=os.environ["COGNITE_TOKEN_URL"],
                    client_id=os.environ["COGNITE_CLIENT_ID"],
                    client_secret=os.environ["COGNITE_CLIENT_SECRET"],
                    scopes=[os.environ["COGNITE_TOKEN_SCOPES"]],
                )
            )
        )
        url = f"/api/v1/projects/{project}/documents/semantic/search"
        headers = {
            "cdf-version": "beta",
        }

        while True:
            try:
                return client.post(url, json=body, headers=headers)
            except Exception as e:
                print(e)
                time.sleep(5)



