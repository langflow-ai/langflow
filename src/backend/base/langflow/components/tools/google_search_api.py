from langchain_google_community import GoogleSearchAPIWrapper

from langflow.custom import Component
from langflow.io import IntInput, MultilineInput, Output, SecretStrInput
from langflow.schema import DataFrame


class GoogleSearchAPIComponent(Component):
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
        google_api_key = self.google_api_key
        google_cse_id = self.google_cse_id

        if not google_api_key or google_api_key == "from langflow.io import Output":
            return DataFrame({"error": ["Invalid Google API Key. Please provide a valid API key."]})

        if not google_cse_id or google_cse_id == "from langflow.io import Output":
            return DataFrame({"error": ["Invalid Google CSE ID. Please provide a valid CSE ID."]})

        try:
            wrapper = GoogleSearchAPIWrapper(
                google_api_key=google_api_key,
                google_cse_id=google_cse_id,
                k=self.k,
            )
            results = wrapper.results(query=self.input_value, num_results=self.k)
        except (ValueError, ConnectionError, RuntimeError) as e:
            error_message = f"Error occurred while searching: {e!s}"
            self.status = error_message
            return DataFrame({"error": [error_message]})
        else:
            return results

    def build(self):
        return self.search_google
