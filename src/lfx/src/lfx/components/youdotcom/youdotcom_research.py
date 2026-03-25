import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output

USER_AGENT = "langflow-youdotcom/1.0"


class YouDotComResearchComponent(Component):
    """You.com Research component for multi-step reasoning with comprehensive web research.

    This component calls the You.com Research API to perform multi-step reasoning
    with comprehensive web research. It takes a complex question and returns a
    detailed markdown answer with inline citations and sources.

    Attributes:
        display_name: Human-readable name for the component.
        description: Description of what the component does.
        icon: Icon identifier for the UI.
        inputs: List of input parameters (api_key, query, research_effort).
        outputs: List of output methods (research_combined, research_answer, research_sources).
    """

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
            info="Your You.com API key. Get one at https://you.com/platform/api-keys",
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
        Output(display_name="Combined", name="combined", method="research_combined"),
        Output(display_name="Answer", name="answer", method="research_answer"),
        Output(display_name="Sources", name="sources_dataframe", method="research_sources"),
    ]

    def _call_research_api(self) -> dict:
        """Call the Research API and return the raw response."""
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
        return response.json()

    def _format_sources_markdown(self, sources: list[dict]) -> str:
        """Format sources as a markdown list."""
        if not sources:
            return ""
        lines = ["\n\n---\n\n**Sources:**"]
        for i, source in enumerate(sources, 1):
            title = source.get("title", "Untitled")
            url = source.get("url", "")
            lines.append(f"{i}. [{title}]({url})")
        return "\n".join(lines)

    def research_combined(self) -> Message:
        """Perform research and return combined answer with sources.

        Returns:
            Message: A Message containing the research answer with citations appended.
        """
        try:
            research_results = self._call_research_api()
            output = research_results.get("output", {})
            content = output.get("content", "")
            sources = output.get("sources", [])
            content += self._format_sources_markdown(sources)
        except httpx.TimeoutException:
            content = (
                "Request timed out (300s). Research queries can take several minutes "
                "with higher effort levels. Try using 'lite' or 'standard' effort."
            )
            logger.error(content)
        except httpx.HTTPStatusError as exc:
            content = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            logger.error(content)
        except httpx.RequestError as exc:
            content = f"Request error occurred: {exc}"
            logger.error(content)
        except ValueError as exc:
            content = f"Invalid response format: {exc}"
            logger.error(content)

        self.status = content
        return Message(text=content)

    def research_answer(self) -> Message:
        """Perform research and return the answer only.

        Returns:
            Message: A Message containing the research answer.
        """
        try:
            research_results = self._call_research_api()
            output = research_results.get("output", {})
            content = output.get("content", "")
        except httpx.TimeoutException:
            content = (
                "Request timed out (300s). Research queries can take several minutes "
                "with higher effort levels. Try using 'lite' or 'standard' effort."
            )
            logger.error(content)
        except httpx.HTTPStatusError as exc:
            content = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            logger.error(content)
        except httpx.RequestError as exc:
            content = f"Request error occurred: {exc}"
            logger.error(content)
        except ValueError as exc:
            content = f"Invalid response format: {exc}"
            logger.error(content)

        self.status = content
        return Message(text=content)

    def research_sources(self) -> DataFrame:
        """Perform research and return sources as a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the research sources with titles, URLs, and snippets.
        """
        try:
            research_results = self._call_research_api()
            output = research_results.get("output", {})
            sources = output.get("sources", [])

            data_results = []
            for source in sources:
                source_data = {
                    "title": source.get("title", ""),
                    "url": source.get("url", ""),
                    "snippets": source.get("snippets", []),
                }
                data_results.append(Data(text=source.get("title", ""), data=source_data))

        except httpx.TimeoutException:
            error_message = "Request timed out (300s). Try using 'lite' or 'standard' effort."
            logger.error(error_message)
            return DataFrame([Data(text=error_message, data={"error": error_message})])
        except httpx.HTTPStatusError as exc:
            error_message = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            logger.error(error_message)
            return DataFrame([Data(text=error_message, data={"error": error_message})])
        except httpx.RequestError as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return DataFrame([Data(text=error_message, data={"error": error_message})])
        except ValueError as exc:
            error_message = f"Invalid response format: {exc}"
            logger.error(error_message)
            return DataFrame([Data(text=error_message, data={"error": error_message})])
        else:
            self.status = data_results
            return DataFrame(data_results)
