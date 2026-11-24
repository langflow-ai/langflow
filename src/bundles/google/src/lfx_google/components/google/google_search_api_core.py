from langchain_google_community import GoogleSearchAPIWrapper
from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MultilineInput, Output, SecretStrInput
from lfx.schema.dataframe import DataFrame

# Google closed the Custom Search JSON API to new customers and shuts it down for
# existing customers on this date.
_SUNSET_DATE = "January 1, 2027"

# Other components that return Google results, in the "<bundle>.<Class>" form the
# canvas Legacy banner reads. Serper ships in this bundle, so it is present on every
# install; the others are opt-in bundles and the banner skips them when absent.
_REPLACEMENTS = [
    "google.GoogleSerperAPICore",
    "searchapi.SearchComponent",
    "serpapi.Serp",
    "serply.SerplySearchComponent",
]


class GoogleSearchAPICore(Component):
    """Deprecated Custom Search JSON API client, kept so saved flows still load."""

    display_name = "Google Search API"
    description = (
        "Deprecated. Call Google's Custom Search JSON API and return results as a DataFrame. "
        f"Google closed this API to new customers, and it stops working on {_SUNSET_DATE}. "
        "Use Serper, SearchApi, or SerpApi instead."
    )
    documentation: str = "https://docs.langflow.org/bundles-google#google-search-api"
    icon = "Google"
    legacy: bool = True
    replacement = _REPLACEMENTS

    inputs = [
        SecretStrInput(
            name="google_api_key",
            display_name="Google API Key",
            required=True,
        ),
        SecretStrInput(
            name="google_cse_id",
            display_name="Google CSE ID",
            info=(
                "The ID of your Programmable Search Engine. Google's Custom Search JSON API is closed "
                f"to new customers and stops working on {_SUNSET_DATE}."
            ),
            required=True,
        ),
        MultilineInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
        ),
        IntInput(
            name="k",
            display_name="Number of results",
            value=4,
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Results",
            name="results",
            type_=DataFrame,
            method="search_google",
        ),
    ]

    def search_google(self) -> DataFrame:
        """Search Google using the provided query."""
        if not self.google_api_key:
            return DataFrame([{"error": "Invalid Google API Key"}])

        if not self.google_cse_id:
            return DataFrame([{"error": "Invalid Google CSE ID"}])

        try:
            wrapper = GoogleSearchAPIWrapper(
                google_api_key=self.google_api_key, google_cse_id=self.google_cse_id, k=self.k
            )
            results = wrapper.results(query=self.input_value, num_results=self.k)
            return DataFrame(results)
        except (ValueError, KeyError) as e:
            return DataFrame([{"error": f"Invalid configuration: {e!s}"}])
        except ConnectionError as e:
            return DataFrame([{"error": f"Connection error: {e!s}"}])
        except RuntimeError as e:
            return DataFrame([{"error": f"Error occurred while searching: {e!s}"}])

    def build(self):
        return self.search_google
