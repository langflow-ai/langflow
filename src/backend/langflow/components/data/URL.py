from typing import Any, Dict, Optional

from langchain_community.document_loaders.url import UnstructuredURLLoader

from langflow import CustomComponent
from langflow.schema import Record


class URLComponent(CustomComponent):
    display_name = "URL"
    description = "Load a URL."

    def build_config(self) -> Dict[str, Any]:
        return {
            "urls": {"display_name": "URL"},
        }

    async def build(
        self,
        urls: list[str],
    ) -> Optional[Record]:

        loader = UnstructuredURLLoader(urls=urls)
        docs = loader.load()
        records = self.to_records(docs)
        return records
