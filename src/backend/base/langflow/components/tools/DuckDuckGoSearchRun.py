from langflow.base.io.text import TextComponent
from langflow.io import StrInput, IntInput, Output
from langflow.schema.message import Message
from langchain_community.tools import DuckDuckGoSearchRun

class DuckDuckGoSearchComponent(TextComponent):
    display_name = "DuckDuckGo Search"
    description = "Perform web searches using the DuckDuckGo search engine."
    icon = "DuckDuckGo"
    name = "DuckDuckGoSearch"

    inputs = [
        StrInput(
            name="query",
            display_name="Search Query",
            required=True,
            info="The search query to be executed.",
        ),
        IntInput(
            name="num_results",
            display_name="Number of Results",
            value=5,
            info="The number of search results to return (default: 5).",
        ),
    ]

    outputs = [
        Output(display_name="Search Results", name="search_results", method="search_response"),
    ]

    def search_response(self) -> Message:
        try:
            search_tool = DuckDuckGoSearchRun()
            results = search_tool.run(f"{self.query} (site:*)")
            
            # Split the results into a list and limit to the specified number
            result_list = results.split('\n')[:self.num_results]
            
            # Format the results as a string
            formatted_results = "\n\n".join([f"{i+1}. {result}" for i, result in enumerate(result_list)])
            
            message_content = f"Search results for '{self.query}':\n\n{formatted_results}"
            
            self.status = message_content
            return Message(text=message_content)
        except Exception as e:
            error_message = f"An error occurred during the search: {str(e)}"
            self.status = error_message
            return Message(content=error_message)
