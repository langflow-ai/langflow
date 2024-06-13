from langflow.custom import Component
from langflow.inputs import StrInput
from langflow.template import Output
from langflow.schema import Data
from langchain_community.document_loaders.web_base import WebBaseLoader


class URLComponent(Component):
    display_name = "URL"
    description = "Fetch content from one or more URLs."
    icon = "layout-template"

    inputs = [
        StrInput(
            name="urls",
            display_name="URLs",
            info="Enter one or more URLs, separated by commas.",
            value="",
            is_list=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="fetch_content"),
    ]

    def fetch_content(self) -> Data:
        urls = [url.strip() for url in self.urls if url.strip()]
        loader = WebBaseLoader(web_paths=urls)
        docs = loader.load()
        data = [Data(content=doc.page_content) for doc in docs]
        self.status = data
        return data
