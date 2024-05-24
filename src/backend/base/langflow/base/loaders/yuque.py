from typing import Dict, Any

from langchain_core.documents import Document

from langflow.helpers.YuQueDocLoaderExec import YuQueDocLoaderExec
from langflow.interface.custom.custom_component import CustomComponent


class YuQueDocLoader(CustomComponent):
    display_name: str = "YuQueDocLoader"
    description: str = "Load from yuQue（https://www.yuque.com） URL"

    def build_config(self) -> Dict[str, Any]:
        return {
            "doc_type": {
                "display_name": "Document Type",
                "options": [
                    "Knowledge",
                    "Document",
                ],
                "info": "Please select a single document or a knowledge base",
                "required": True,
            },
            "token": {
                "display_name": "Token",
                "required": True,
            },
            "url": {
                "display_name": "URL",
                "required": True,
                "info": "Please Enter the URL after [https://www.yuque.com/]"
            },
            "code": {"show": "true"},
        }

    def build(
            self,
            doc_type: str,
            token: str,
            url: str,
    ) -> Document:
        return YuQueDocLoaderExec(
            token=token,
            url=url,
            doc_type=doc_type,
        ).load()
