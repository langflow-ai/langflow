import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output


class SerpdiveSearchComponent(Component):
    display_name = "SERPdive Search API"
    description = """**SERPdive** is a web search API for AI agents: one call returns the \
        extracted, answer-ready content of each source page instead of a list of links."""
    documentation = "https://serpdive.com/docs"
    icon = "SERPdiveIcon"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="SERPdive API Key",
            required=True,
            info="Your SERPdive API Key. Free at https://serpdive.com/dashboard/keys.",
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query you want to execute with SERPdive. Any language: localization is automatic.",
            tool_mode=True,
        ),
        DropdownInput(
            name="model",
            display_name="Retrieval Depth",
            info=(
                "The retrieval depth. 'mako' returns the fact-carrying sentences of each source; "
                "'moby' returns the full readable content of every page."
            ),
            options=["mako", "moby"],
            value="mako",
            advanced=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Hard cap on delivered results, keeping the best-ranked ones (1-10). Leave empty for all relevant.",
            value=5,
            advanced=True,
        ),
        BoolInput(
            name="include_answer",
            display_name="Include Answer",
            info="Also return a written answer built from the sources. Included in the price, no extra credits.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def fetch_content(self) -> list[Data]:
        try:
            url = "https://api.serpdive.com/v1/search"
            headers = {
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            }

            payload: dict = {"query": self.query}

            if self.model:
                payload["model"] = self.model
            if self.include_answer:
                payload["answer"] = True
            if self.max_results:
                payload["max_results"] = int(self.max_results)

            # Moby reads whole pages; the API docs recommend at least an 80 s client timeout.
            with httpx.Client(timeout=90.0) as client:
                response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            search_results = response.json()

            data_results = []

            if self.include_answer and search_results.get("answer"):
                data_results.append(Data(text=search_results["answer"]))

            for result in search_results.get("results", []):
                content = result.get("content", "")
                result_data = {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "content": content,
                }
                if result.get("date"):
                    result_data["date"] = result["date"]

                data_results.append(Data(text=content, data=result_data))

            if search_results.get("extra_info"):
                data_results.append(Data(text="Direct answer data", data={"extra_info": search_results["extra_info"]}))

        except httpx.TimeoutException:
            error_message = "Request timed out (90s). Try the 'mako' retrieval depth or a shorter query."
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except httpx.HTTPStatusError as exc:
            error_message = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except httpx.RequestError as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except ValueError as exc:
            error_message = f"Invalid response format: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        else:
            self.status = data_results
            return data_results

    def fetch_content_dataframe(self) -> DataFrame:
        data = self.fetch_content()
        return DataFrame(data)
