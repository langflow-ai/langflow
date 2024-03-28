from typing import Any, Dict

from langchain_community.document_loaders.web_base import WebBaseLoader

from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record


class URLComponent(CustomComponent):
    display_name = "URL"
    description = "Fetch text content given one or more URLs."

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
