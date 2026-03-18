import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

USER_AGENT = "langflow-youdotcom/1.0"


class YouDotComResearchComponent(Component):
    display_name = "You.com Research"
    description = (
        "**You.com Research** performs multi-step reasoning with comprehensive web research. "
        "Returns a detailed markdown answer with inline citations and sources."
    )
    icon = "YouDotCom"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="You.com API Key",
            required=True,
            info="Your You.com API key. Get one at https://docs.you.com",
        ),
        MessageTextInput(
            name="query",
            display_name="Research Query",
            info="The research question to investigate (max 40,000 characters).",
            tool_mode=True,
        ),
        DropdownInput(
            name="research_effort",
            display_name="Research Effort",
            info="Controls depth and time spent researching. Higher effort = more thorough but slower.",
            options=["lite", "standard", "deep", "exhaustive"],
            value="standard",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def fetch_content(self) -> list[Data]:
        try:
            url = "https://api.you.com/v1/research"
            headers = {
                "X-API-Key": self.api_key,
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            }

            payload = {
                "input": self.query,
                "research_effort": self.research_effort,
            }

            with httpx.Client(timeout=300.0) as client:
                response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            research_results = response.json()

            output = research_results.get("output", {})
            content = output.get("content", "")
            sources = output.get("sources", [])

            result_data = {
                "content": content,
                "content_type": output.get("content_type", "text"),
                "sources": sources,
            }

            data_results = [Data(text=content, data=result_data)]

        except httpx.TimeoutException:
            error_message = (
                "Request timed out (300s). Research queries can take several minutes "
                "with higher effort levels. Try using 'lite' or 'standard' effort."
            )
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
