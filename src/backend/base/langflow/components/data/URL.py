from typing import Any, Dict

from langchain_community.document_loaders.web_base import WebBaseLoader

from langflow.custom import CustomComponent
from langflow.schema import Data


class URLComponent(CustomComponent):
    display_name = "URL"
    description = "Fetch content from one or more URLs."
    icon = "layout-template"

    def build_config(self) -> Dict[str, Any]:
        return {
            "urls": {"display_name": "URL"},
        }

    def build(
        self,
        urls: list[str],
    ) -> list[Data]:
        loader = WebBaseLoader(web_paths=[url for url in urls if url])
        docs = loader.load()
        data = self.to_data(docs)
        self.status = data
        return data
