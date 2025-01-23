import requests
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper

from langflow.custom import Component
from langflow.inputs import BoolInput, IntInput, MessageTextInput, MultilineInput
from langflow.io import Output
from langflow.schema import DataFrame


class WikipediaComponent(Component):
    """Component for searching and retrieving Wikipedia articles.

    This component allows users to search Wikipedia and returns results
    in a DataFrame format, providing detailed article information.
    """

    display_name = "Wikipedia"
    description = "Search Wikipedia API and return results as a DataFrame."
    icon = "Wikipedia"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
            required=True,
            info="Search query for Wikipedia articles",
        ),
        MessageTextInput(
            name="lang",
            display_name="Language",
            value="en",
            required=True,
        ),
        IntInput(
            name="k",
            display_name="Number of results",
            value=4,
            advanced=True,
        ),
        BoolInput(
            name="load_all_available_meta",
            display_name="Load all available meta",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="doc_content_chars_max",
            display_name="Document content characters max",
            value=4000,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Results",
            name="results",
            type_=DataFrame,
            method="search_wikipedia",
        ),
    ]

    def search_wikipedia(self) -> DataFrame:
        """Search Wikipedia and return results as a DataFrame."""
        try:
            wrapper = self._build_wrapper()
            docs = wrapper.load(self.input_value)

            if not docs:
                return DataFrame([{"error": "No Wikipedia articles found for the given query."}])

            # Transform documents into a DataFrame
            results = [
                {
                    "title": doc.metadata.get("title", ""),
                    "source": doc.metadata.get("source", ""),
                    "content": (
                        doc.page_content[: self.doc_content_chars_max]
                        if self.doc_content_chars_max
                        else doc.page_content
                    ),
                    "summary": doc.page_content[:500],  # Short summary
                }
                for doc in docs
            ]

            return DataFrame(results)

        except (ValueError, KeyError) as e:
            error_message = f"Error parsing Wikipedia response: {e!s}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
        except requests.RequestException as e:
            error_message = f"Error making request to Wikipedia: {e!s}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])

    def _build_wrapper(self) -> WikipediaAPIWrapper:
        return WikipediaAPIWrapper(
            top_k_results=self.k or 4,
            lang=self.lang,
            load_all_available_meta=self.load_all_available_meta,
            doc_content_chars_max=self.doc_content_chars_max,
        )
