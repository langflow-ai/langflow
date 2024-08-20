from typing import Any
import requests
import json

from pydantic.v1 import Field, create_model

from langchain.agents import Tool
from langchain_core.tools import StructuredTool
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import MessageTextInput, MultiselectInput, DropdownInput, IntInput
from langflow.schema.dotdict import dotdict
from langflow.io import Output


class SearXNGToolComponent(LCToolComponent):
    search_headers: dict = {}
    display_name = "SearXNG Search Tool"
    description = "A component that searches for tools using SearXNG."
    name = "SearXNGTool"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="URL",
            value="http://localhost",
            required=True,
            refresh_button=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=10,
            required=True,
        ),
        MultiselectInput(
            name="categories",
            display_name="Categories",
            options=[],
            value=[],
        ),
        DropdownInput(
            name="language",
            display_name="Language",
            options=[],
        ),
    ]

    outputs = [
        Output(display_name="Tool", name="result_tool", method="build_tool"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name is None:
            return build_config

        if field_name != "url":
            return build_config

        try:
            url = f"{field_value}/config"

            response = requests.get(url=url, headers=self.search_headers.copy())
            data = None
            if response.headers.get("Content-Encoding") == "zstd":
                data = json.loads(response.content)
            else:
                data = response.json()
            build_config["categories"]["options"] = data["categories"].copy()
            for selected_category in build_config["categories"]["value"]:
                if selected_category not in build_config["categories"]["options"]:
                    build_config["categories"]["value"].remove(selected_category)
            languages = []
            for language in data["locales"]:
                languages.append(language)
            build_config["language"]["options"] = languages.copy()
        except Exception as e:
            self.status = f"Failed to extract names: {str(e)}"
            build_config["categories"]["options"] = ["Failed to parse", str(e)]
        return build_config

    def build_tool(self) -> Tool:
        class SearxSearch:
            _url: str = ""
            _categories: list[str] = []
            _language: str = ""
            _headers: dict = {}
            _max_results: int = 10

            @staticmethod
            def search(query: str, categories: list[str] = []) -> list:
                if not SearxSearch._categories and not categories:
                    raise ValueError("No categories provided.")
                all_categories = SearxSearch._categories + list(set(categories) - set(SearxSearch._categories))
                try:
                    url = f"{SearxSearch._url}/"
                    headers = SearxSearch._headers.copy()
                    response = requests.get(
                        url=url,
                        headers=headers,
                        params={
                            "q": query,
                            "categories": ",".join(all_categories),
                            "language": SearxSearch._language,
                            "format": "json",
                        },
                    ).json()

                    results = []
                    num_results = min(SearxSearch._max_results, len(response["results"]))
                    for i in range(num_results):
                        results.append(response["results"][i])
                    return results
                except Exception as e:
                    return [f"Failed to search: {str(e)}"]

        SearxSearch._url = self.url
        SearxSearch._categories = self.categories.copy()
        SearxSearch._language = self.language
        SearxSearch._headers = self.search_headers.copy()
        SearxSearch._max_results = self.max_results

        _globals = globals()
        _local = {}
        _local["SearxSearch"] = SearxSearch
        _globals.update(_local)

        schema_fields = {
            "query": (str, Field(..., description="The query to search for.")),
            "categories": (list[str], Field(default=[], description="The categories to search in.")),
        }

        SearxSearchSchema = create_model("SearxSearchSchema", **schema_fields)  # type: ignore

        tool = StructuredTool.from_function(
            func=_local["SearxSearch"].search,
            args_schema=SearxSearchSchema,
            name="searxng_search_tool",
            description="A tool that searches for tools using SearXNG.\nThe available categories are: "
            + ", ".join(self.categories),
        )
        return tool
