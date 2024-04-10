from typing import Callable, Union

from langchain_community.utilities.wikipedia import WikipediaAPIWrapper

from langflow.interface.custom.custom_component import CustomComponent

# Assuming WikipediaAPIWrapper is a class that needs to be imported.
# The import statement is not included as it is not provided in the JSON
# and the actual implementation details are unknown.


class WikipediaAPIWrapperComponent(CustomComponent):
    display_name = "WikipediaAPIWrapper"
    description = "Wrapper around WikipediaAPI."

    def build_config(self):
        return {}

    def build(
        self,
        top_k_results: int = 3,
        lang: str = "en",
        load_all_available_meta: bool = False,
        doc_content_chars_max: int = 4000,
    ) -> Union[WikipediaAPIWrapper, Callable]:
        return WikipediaAPIWrapper(  # type: ignore
            top_k_results=top_k_results,
            lang=lang,
            load_all_available_meta=load_all_available_meta,
            doc_content_chars_max=doc_content_chars_max,
        )
