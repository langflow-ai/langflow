from datetime import date

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output

from linkup import LinkupClient

DEPTH_OPTIONS = ["fast", "standard", "deep"]
DEFAULT_DEPTH = "standard"
DEFAULT_MAX_RESULTS = 10
# Deep searches run several retrieval steps and can take tens of seconds.
REQUEST_TIMEOUT_SECONDS = 120.0


class LinkupSearchComponent(Component):
    """Component for searching the web with the Linkup API."""

    display_name = "Linkup Search"
    description = (
        "Search the web in real time with Linkup and return relevant, citable sources, "
        "or a sourced answer to the query."
    )
    documentation = "https://docs.linkup.so/pages/documentation/api-reference/endpoint/post-search"
    icon = "Linkup"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            required=True,
            info="The search query to execute with Linkup.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="linkup_api_key",
            display_name="Linkup API Key",
            required=True,
            info="Your Linkup API key. Get one at https://app.linkup.so.",
            password=True,
        ),
        DropdownInput(
            name="depth",
            display_name="Depth",
            options=DEPTH_OPTIONS,
            value=DEFAULT_DEPTH,
            info="Latency vs. thoroughness tradeoff. `standard` suits most queries; `deep` runs an iterative search "
            "for complex, multi-step questions.",
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=DEFAULT_MAX_RESULTS,
            advanced=True,
            info="Maximum number of results to return. 0 uses Linkup's default.",
        ),
        MessageTextInput(
            name="include_domains",
            display_name="Include Domains",
            value="",
            advanced=True,
            info="Comma-separated allowlist of domains.",
        ),
        MessageTextInput(
            name="exclude_domains",
            display_name="Exclude Domains",
            value="",
            advanced=True,
            info="Comma-separated denylist of domains.",
        ),
        MessageTextInput(
            name="from_date",
            display_name="From Date",
            value="",
            advanced=True,
            info="ISO date (YYYY-MM-DD). Only return results published on or after this date.",
        ),
        MessageTextInput(
            name="to_date",
            display_name="To Date",
            value="",
            advanced=True,
            info="ISO date (YYYY-MM-DD). Only return results published on or before this date.",
        ),
    ]

    outputs = [
        # The method names are also the tool names in tool mode.  Keep them
        # specific so an Agent can hold these alongside other search tools.
        Output(
            display_name="Search Results",
            name="search_results",
            method="linkup_search",
            info="Search the web with Linkup and return a table of sources with title, URL and content.",
        ),
        Output(
            display_name="Sourced Answer",
            name="sourced_answer",
            method="linkup_sourced_answer",
            info="Search the web with Linkup and return a natural-language answer with its sources.",
        ),
    ]

    @staticmethod
    def _split_csv(raw: str | None) -> list[str] | None:
        items = [s.strip() for s in (raw or "").split(",") if s.strip()]
        return items or None

    @staticmethod
    def _parse_date(raw: str | None, field: str) -> date | None:
        value = (raw or "").strip()
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError as e:
            msg = f"{field} must be an ISO date (YYYY-MM-DD), got {value!r}."
            raise ValueError(msg) from e

    def _build_client(self) -> LinkupClient:
        if not self.linkup_api_key:
            msg = "Linkup API key is required. Set the Linkup API Key input."
            raise ValueError(msg)
        return LinkupClient(api_key=self.linkup_api_key)

    def _search_kwargs(self) -> dict:
        kwargs: dict = {"depth": self.depth or DEFAULT_DEPTH, "timeout": REQUEST_TIMEOUT_SECONDS}
        if self.max_results and self.max_results > 0:
            kwargs["max_results"] = int(self.max_results)
        include_domains = self._split_csv(self.include_domains)
        if include_domains:
            kwargs["include_domains"] = include_domains
        exclude_domains = self._split_csv(self.exclude_domains)
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains
        from_date = self._parse_date(self.from_date, "From Date")
        if from_date:
            kwargs["from_date"] = from_date
        to_date = self._parse_date(self.to_date, "To Date")
        if to_date:
            kwargs["to_date"] = to_date
        return kwargs

    def _search(self, output_type: str):
        query = (self.query or "").strip()
        if not query:
            msg = "Search query is required."
            raise ValueError(msg)
        client = self._build_client()
        return client.search(query, output_type=output_type, **self._search_kwargs())

    def linkup_search(self) -> DataFrame:
        """Run the search and return the results as a DataFrame."""
        response = self._search("searchResults")
        results = [
            Data(
                text=result.content,
                data={"title": result.name, "url": result.url, "content": result.content},
            )
            for result in response.results
            if result.type == "text"
        ]
        self.status = results
        return DataFrame(results)

    def linkup_sourced_answer(self) -> Message:
        """Run the search and return Linkup's answer followed by its sources."""
        response = self._search("sourcedAnswer")
        text = response.answer
        if response.sources:
            sources = "\n".join(f"- [{source.name}]({source.url})" for source in response.sources)
            text = f"{text}\n\nSources:\n{sources}"
        message = Message(text=text)
        self.status = message
        return message
