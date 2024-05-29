from typing import Any, Dict

from langchain_community.document_loaders.web_base import WebBaseLoader

from langflow.custom import CustomComponent
from langflow.schema import Record


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
    ) -> list[Record]:
        loader = WebBaseLoader(web_paths=urls)
        docs = loader.load()
        records = self.to_records(docs)
        self.status = records
        return records
