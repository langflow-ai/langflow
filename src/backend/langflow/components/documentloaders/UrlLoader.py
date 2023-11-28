from typing import List

from langchain import document_loaders
from langchain.schema import Document
from langflow import CustomComponent


class UrlLoaderComponent(CustomComponent):
    display_name: str = "Url Loader"
    description: str = "Generic Url Loader Component"

    def build_config(self):
        return {
            "web_path": {
                "display_name": "Url",
                "required": True,
            },
            "loader": {
                "display_name": "Loader",
                "is_list": True,
                "required": True,
                "options": [
                    "AZLyricsLoader",
                    "CollegeConfidentialLoader",
                    "GitbookLoader",
                    "HNLoader",
                    "IFixitLoader",
                    "IMSDbLoader",
                    "WebBaseLoader",
                ],
                "value": "WebBaseLoader",
            },
            "code": {"show": False},
        }

    def build(self, web_path: str, loader: str) -> List[Document]:
        try:
            loader_instance = getattr(document_loaders, loader)(web_path=web_path)
        except Exception as e:
            raise ValueError(f"No loader found for: {web_path}") from e
        docs = loader_instance.load()
        avg_length = sum(len(doc.page_content) for doc in docs if hasattr(doc, "page_content")) / len(docs)
        self.status = f"""{len(docs)} documents)
        \nAvg. Document Length (characters): {int(avg_length)}
        Documents: {docs[:3]}..."""
        return docs
