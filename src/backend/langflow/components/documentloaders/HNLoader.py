
from langchain import CustomComponent
from langchain.document_loaders import BaseLoader
from typing import Optional, Dict

class HNLoaderComponent(CustomComponent):
    display_name = "HNLoader"
    description = "Load `Hacker News` data."

    def build_config(self):
        return {
            "metadata": {
                "display_name": "Metadata",
                "default": {},
                "required": False
            },
            "web_path": {
                "display_name": "Web Page",
                "required": True
            },
        }

    def build(
        self, 
        web_path: str,
        metadata: Optional[Dict] = None, 
    ) -> BaseLoader:
        # Assuming that there's a specific loader for Hacker News
        # as BaseLoader does not take a web_path argument
        # The HackerNewsLoader needs to be defined somewhere in the actual implementation
        return HackerNewsLoader(metadata=metadata, web_path=web_path)
