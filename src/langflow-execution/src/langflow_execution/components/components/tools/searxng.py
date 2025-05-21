import json
from collections.abc import Sequence
from typing import Any

import requests
from langchain.agents import Tool
from langchain_core.tools import StructuredTool
from loguru import logger
from pydantic.v1 import Field, create_model

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import DropdownInput, IntInput, MessageTextInput, MultiselectInput
from langflow.io import Output
from langflow.schema.dotdict import dotdict


class SearXNGToolComponent(LCToolComponent):
    search_headers: dict = {}
    display_name = "SearXNG Search"
    description = "A component that searches for tools using SearXNG."
    name = "SearXNGTool"
    legacy: bool = True

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

            response = requests.get(url=url, headers=self.search_headers.copy(), timeout=10)
            data = None
            if response.headers.get("Content-Encoding") == "zstd":
                data = json.loads(response.content)
            else:
                data = response.json()
            build_config["categories"]["options"] = data["categories"].copy()
            for selected_category in build_config["categories"]["value"]:
                if selected_category not in build_config["categories"]["options"]:
                    build_config["categories"]["value"].remove(selected_category)
            languages = list(data["locales"])
            build_config["language"]["options"] = languages.copy()
        except Exception as e:  # noqa: BLE001
            self.status = f"Failed to extract names: {e}"
            logger.opt(exception=True).debug(self.status)
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
            def search(query: str, categories: Sequence[str] = ()) -> list:
                if not SearxSearch._categories and not categories:
                    msg = "No categories provided."
                    raise ValueError(msg)
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
                        timeout=10,
                    ).json()

                    num_results = min(SearxSearch._max_results, len(response["results"]))
                    return [response["results"][i] for i in range(num_results)]
                except Exception as e:  # noqa: BLE001
                    logger.opt(exception=True).debug("Error running SearXNG Search")
                    return [f"Failed to search: {e}"]

        SearxSearch._url = self.url
        SearxSearch._categories = self.categories.copy()
        SearxSearch._language = self.language
        SearxSearch._headers = self.search_headers.copy()
        SearxSearch._max_results = self.max_results

        globals_ = globals()
        local = {}
        local["SearxSearch"] = SearxSearch
        globals_.update(local)

        schema_fields = {
            "query": (str, Field(..., description="The query to search for.")),
            "categories": (
                list[str],
                Field(default=[], description="The categories to search in."),
            ),
        }

        searx_search_schema = create_model("SearxSearchSchema", **schema_fields)

        return StructuredTool.from_function(
            func=local["SearxSearch"].search,
            args_schema=searx_search_schema,
            name="searxng_search_tool",
            description="A tool that searches for tools using SearXNG.\nThe available categories are: "
            + ", ".join(self.categories),
        )
