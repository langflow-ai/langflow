import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output


class BochaSearchComponent(Component):
    display_name = "Bocha Web Search"
    description = "Search the web using Bocha Web Search API."
    icon = "Search"
    name = "BochaWebSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Bocha API Key",
            required=True,
            info="Your Bocha API Key from open.bochaai.com.",
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            tool_mode=True,
            required=True,
        ),
        BoolInput(
            name="summary",
            display_name="Include Summary",
            value=True,
            advanced=True,
        ),
        DropdownInput(
            name="freshness",
            display_name="Freshness",
            options=["noLimit", "oneYear", "oneMonth", "oneWeek", "oneDay"],
            value="noLimit",
            advanced=True,
        ),
        IntInput(
            name="count",
            display_name="Number of Results",
            value=10,
            required=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def fetch_content(self) -> list[Data]:
        url = "https://api.bochaai.com/v1/web-search"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": self.query,
            "summary": self.summary,
            "freshness": self.freshness or "noLimit",
            "count": min(int(self.count), 50),
        }

        try:
            with httpx.Client(timeout=90.0) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            result = response.json()
            web_pages = result.get("data", {}).get("webPages", {}).get("value", [])

            data_results = []
            for item in web_pages:
                snippet = item.get("snippet") or ""
                summary = item.get("summary") or ""
                text = summary or snippet

                data_results.append(
                    Data(
                        text=text,
                        data={
                            "title": item.get("name"),
                            "url": item.get("url"),
                            "snippet": snippet,
                            "summary": summary,
                            "site_name": item.get("siteName"),
                            "site_icon": item.get("siteIcon"),
                            "date_published": item.get("datePublished"),
                        },
                    )
                )

        except httpx.TimeoutException:
            msg = "Bocha request timed out."
        except httpx.HTTPStatusError as exc:
            msg = f"Bocha HTTP error: {exc.response.status_code} - {exc.response.text}"
        except httpx.RequestError as exc:
            msg = f"Bocha request failed: {exc}"
        else:
            self.status = data_results
            return data_results

        logger.error(msg)
        return [Data(text=msg, data={"error": msg})]

    def fetch_content_dataframe(self) -> DataFrame:
        return DataFrame(self.fetch_content())
