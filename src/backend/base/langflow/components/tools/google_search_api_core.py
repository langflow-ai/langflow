from langchain_google_community import GoogleSearchAPIWrapper

from langflow.custom import Component
from langflow.io import IntInput, MultilineInput, Output, SecretStrInput
from langflow.schema import DataFrame


class GoogleSearchAPICore(Component):
    display_name = "Google Search API"
    description = "Call Google Search API and return results as a DataFrame."
    icon = "Google"

    inputs = [
        SecretStrInput(
            name="google_api_key",
            display_name="Google API Key",
            required=True,
        ),
        SecretStrInput(
            name="google_cse_id",
            display_name="Google CSE ID",
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
