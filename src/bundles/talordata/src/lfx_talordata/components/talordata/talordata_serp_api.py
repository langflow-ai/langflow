from __future__ import annotations

from typing import Any

import requests
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DictInput, DropdownInput, IntInput, MultilineInput, SecretStrInput, StrInput
from lfx.io import Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class TalordataSERPAPIComponent(Component):
    display_name = "Talordata SERP API"
    description = "Call Talordata SERP API to retrieve structured search engine results."
    documentation = "https://docs.talordata.com/serp-api/query-parameters"
    icon = "Search"

    inputs = [
        SecretStrInput(name="api_key", display_name="Talordata API Key", required=True),
        MultilineInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
        ),
        DropdownInput(
            name="engine",
            display_name="Engine",
            value="google",
            options=["google", "bing", "yandex", "duckduckgo"],
        ),
        IntInput(name="max_results", display_name="Max Results", value=5, advanced=True),
        StrInput(name="gl", display_name="Country", value="us", advanced=True),
        StrInput(name="hl", display_name="Language", value="en", advanced=True),
        StrInput(name="location", display_name="Location", value="", advanced=True),
        StrInput(name="device", display_name="Device", value="desktop", advanced=True),
        IntInput(name="page", display_name="Page", value=1, advanced=True),
        DictInput(name="search_params", display_name="Search Parameters", advanced=True, is_list=True),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def run_model(self) -> DataFrame:
        return self.fetch_content_dataframe()

    def _build_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "engine": self.engine,
            "q": self.input_value,
            "json": "1",
            "num": self.max_results,
            "gl": self.gl,
            "hl": self.hl,
            "device": self.device,
            "page": self.page,
        }

        if self.location:
            payload["location"] = self.location

        if self.search_params:
            payload.update(self.search_params)

        return payload

    def fetch_content(self) -> list[Data]:
        url = "https://serpapi.talordata.net/serp/v1/request"
        api_key = self.api_key.get_secret_value() if hasattr(self.api_key, "get_secret_value") else self.api_key
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Langflow-Talordata/0.1.0",
        }

        try:
            response = requests.post(url, data=self._build_payload(), headers=headers, timeout=30)
            response.raise_for_status()
            response_json = response.json()
        except requests.RequestException as exc:
            error_data = Data(data={"error": f"Talordata request failed: {exc!s}"})
            self.status = [error_data]
            return [error_data]
        except ValueError as exc:
            error_data = Data(data={"error": f"Talordata returned invalid JSON: {exc!s}"})
            self.status = [error_data]
            return [error_data]

        organic_results = response_json.get("organic_results", [])[: self.max_results]
        results = [
            Data(
                text=result.get("snippet", ""),
                data={
                    "title": result.get("title", ""),
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", ""),
                    "position": result.get("position", index),
                    "engine": self.engine,
                },
            )
            for index, result in enumerate(organic_results, start=1)
        ]

        self.status = results
        return results

    def fetch_content_dataframe(self) -> DataFrame:
        return DataFrame(self.fetch_content())
