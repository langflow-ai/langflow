import httpx

from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

from langchain_core.pydantic_v1 import BaseModel

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import SecretStrInput, StrInput, NestedDictInput, IntInput
from langflow.field_typing import Tool
from langflow.schema import Data


class GleanAPIComponent(LCToolComponent):
    display_name = "Glean Search API"
    description = "Call Glean Search API"
    name = "GleanAPI"

    inputs = [
        StrInput(
            name="glean_api_url",
            display_name="Glean API URL",
            required=True,
        ),
        SecretStrInput(name="glean_access_token", display_name="Glean Access Token", required=True),
        StrInput(name="query", display_name="Query", required=True),
        IntInput(name="page_size", display_name="Page Size", value=10),
        StrInput(name="field_name", display_name="Field Name", required=False),
        NestedDictInput(name="values", display_name="Values", required=False),
    ]

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper()

        return Tool(
            name="glean_search_api",
            description="Search with the Glean API",
            func=wrapper.run
        )
    
    def run_model(self) -> Union[Data, list[Data]]:
        wrapper = self._build_wrapper()

        results = wrapper.results(
            query=self.query,
            page_size=self.page_size,
            field_name=self.field_name,
            values=self.values,
        )

        list_results = results.get("results", [])

        # Build the data
        data = []
        for result in list_results:
            data.append(Data(data=result))

        self.status = data

        return data
    
    def _build_wrapper(self):
        class GleanAPIWrapper(BaseModel):
            """
            Wrapper around Glean API.
            """
            glean_api_url: str
            glean_access_token: str
            act_as: str = "langflow-component@datastax.com"

            def _prepare_request(
                    self,
                    query: str,
                    page_size: int = 10,
                    field_name: Optional[str] = None,
                    values: Optional[List[dict]] = None,
                ) -> dict:

                facet_filters = [{"field_name": field_name, "values": values}]
                if not field_name or not values:
                    facet_filters = []

                return {
                    "url": urljoin(self.glean_api_url, "search"),
                    "headers": {
                        "Authorization": f"Bearer {self.glean_access_token}",
                        "X-Scio-ActAs": self.act_as  # TODO: Update?
                    },
                    "payload": {
                        "query": query,
                        "pageSize": page_size,
                        "requestOptions": {
                            "facetFilters": facet_filters,
                        }
                    }
                }
            
            def run(self, query: str, **kwargs: Any) -> str:
                results = self.results(query, **kwargs)

                return self._result_as_string(results)
            
            def results(self, query: str, **kwargs: Any) -> dict:
                results = self._search_api_results(query, **kwargs)

                return results

            def _search_api_results(
                self,
                query: str,
                **kwargs: Any
            ) -> Dict[str, Any]:
                request_details = self._prepare_request(query, **kwargs)

                response = httpx.post(
                    request_details["url"],
                    json=request_details["payload"],
                    headers=request_details["headers"],
                )

                response.raise_for_status()

                return response.json()

            @staticmethod
            def _result_as_string(result: dict) -> str:
                return str(result)  # TODO: Make pretty

        return GleanAPIWrapper(
            glean_api_url=self.glean_api_url,
            glean_access_token=self.glean_access_token
        )
