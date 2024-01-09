
from langflow import CustomComponent
from typing import Union, Callable
from langchain_community.utilities import WikipediaAPIWrapper

# Assuming WikipediaAPIWrapper is a class that needs to be imported.
# The import statement is not included as it is not provided in the JSON 
# and the actual implementation details are unknown.

class WikipediaAPIWrapperComponent(CustomComponent):
    display_name = "WikipediaAPIWrapper"
    description = "Wrapper around WikipediaAPI."

    def build_config(self):
        return {}

    def build(self) -> Union[WikipediaAPIWrapper, Callable]:
        return WikipediaAPIWrapper()
