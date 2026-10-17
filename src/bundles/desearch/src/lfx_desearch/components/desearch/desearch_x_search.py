import httpx
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_desearch.components.desearch._client import desearch_request, http_error_message

DEFAULT_COUNT = 10
MIN_COUNT = 1
MAX_COUNT = 100


class DesearchXSearchComponent(Component):
    """X (Twitter) post search through the Desearch API."""

    display_name = "Desearch X Search"
    description = "Search X (Twitter) posts by keyword, with optional filters."
    documentation = "https://www.desearch.ai/docs"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Search Query",
            required=True,
            info="Keywords to search for in X posts.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="desearch_api_key",
            display_name="Desearch API Key",
            required=True,
            info="Your Desearch API key. Create one at https://console.desearch.ai/api-keys.",
            password=True,
        ),
        IntInput(
            name="count",
            display_name="Number of Posts",
            value=DEFAULT_COUNT,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=MIN_COUNT, max=MAX_COUNT, step=1, step_type="int"),
            info="How many posts to return (1-100).",
        ),
        DropdownInput(
            name="sort",
            display_name="Sort",
            options=["Top", "Latest"],
            value="Top",
            required=False,
            advanced=True,
            info="Top posts or latest posts first.",
        ),
        MessageTextInput(
            name="user",
            display_name="User",
            required=False,
            advanced=True,
            info="Only posts from this username, without the at sign.",
        ),
        MessageTextInput(
            name="lang",
            display_name="Language",
            required=False,
            advanced=True,
            info="Language code, for example 'en'.",
        ),
        MessageTextInput(
            name="start_date",
            display_name="Start Date",
            required=False,
            advanced=True,
            info="Earliest post date, YYYY-MM-DD (UTC).",
        ),
        MessageTextInput(
            name="end_date",
            display_name="End Date",
            required=False,
            advanced=True,
            info="Latest post date, YYYY-MM-DD (UTC).",
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="desearch_x_search"),
    ]

    def _params(self) -> dict:
        requested = DEFAULT_COUNT if self.count is None else int(self.count)
        params: dict = {
            "query": self.input_value or "",
            "count": max(MIN_COUNT, min(requested, MAX_COUNT)),
            "sort": self.sort if self.sort in ("Top", "Latest") else "Top",
        }
        for field in ("user", "lang", "start_date", "end_date"):
            value = getattr(self, field, None)
            if isinstance(value, str) and value.strip():
                params[field] = value.strip().lstrip("@") if field == "user" else value.strip()
        return params

    def _error_result(self, message: str) -> list[Data]:
        error_data = [Data(text=message, data={"error": message})]
        self.status = error_data
        return error_data

    @staticmethod
    def _post_to_data(post: dict) -> Data:
        user = post.get("user") if isinstance(post.get("user"), dict) else {}
        text = post.get("text", "")
        return Data(
            text=text,
            data={
                "id": post.get("id"),
                "url": post.get("url"),
                "text": text,
                "created_at": post.get("created_at"),
                "username": user.get("username"),
                "like_count": post.get("like_count"),
                "retweet_count": post.get("retweet_count"),
                "reply_count": post.get("reply_count"),
            },
        )

    def fetch_content(self) -> list[Data]:
        """Run the search and return the posts as Data objects."""
        try:
            payload = desearch_request("GET", "/twitter", self.desearch_api_key, params=self._params(), timeout=60)
        except httpx.HTTPStatusError as e:
            return self._error_result(http_error_message(e))
        except (httpx.HTTPError, ValueError) as e:
            return self._error_result(str(e))
        if not isinstance(payload, list):
            return self._error_result("Desearch returned an unexpected response (expected a JSON list).")
        results = [self._post_to_data(post) for post in payload if isinstance(post, dict)]
        self.status = results
        return results

    def desearch_x_search(self) -> DataFrame:
        """Run the search and return the posts as a DataFrame."""
        return DataFrame(self.fetch_content())
