from typing import List
from langflow import CustomComponent
from langchain.document_loaders import AZLyricsLoader
from langchain.document_loaders import CollegeConfidentialLoader
from langchain.document_loaders import GitbookLoader
from langchain.document_loaders import HNLoader
from langchain.document_loaders import IFixitLoader
from langchain.document_loaders import IMSDbLoader
from langchain.document_loaders import WebBaseLoader


from langchain.schema import Document


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
        if loader == "AZLyricsLoader":
            loader_instance = AZLyricsLoader(web_path=web_path)  # type: ignore
        elif loader == "CollegeConfidentialLoader":
            loader_instance = CollegeConfidentialLoader(web_path=web_path)  # type: ignore
        elif loader == "GitbookLoader":
            loader_instance = GitbookLoader(web_page=web_path)  # type: ignore
        elif loader == "HNLoader":
            loader_instance = HNLoader(web_path=web_path)  # type: ignore
        elif loader == "IFixitLoader":
            loader_instance = IFixitLoader(web_path=web_path)  # type: ignore
        elif loader == "IMSDbLoader":
            loader_instance = IMSDbLoader(web_path=web_path)  # type: ignore
        elif loader == "WebBaseLoader":
            loader_instance = WebBaseLoader(web_path=web_path)  # type: ignore

        if loader_instance is None:
            raise ValueError(f"No loader found for: {web_path}")

        return loader_instance.load()
