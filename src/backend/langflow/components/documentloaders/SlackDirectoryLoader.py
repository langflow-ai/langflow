
from langflow import CustomComponent
from typing import Optional, Dict, List
from langchain_core.documents import Document
from langchain_community.document_loaders.slack_directory import SlackDirectoryLoader
class SlackDirectoryLoaderComponent(CustomComponent):
    display_name = "SlackDirectoryLoader"
    description = "Load from a `Slack` directory dump."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/slack"

    def build_config(self):
        return {
            "zip_path": {"display_name": "Path to zip file","field_type": "file","file_types":[".zip"]},
            "metadata": {"display_name": "Metadata", "field_type": "dict"},
            "workspace_url": {"display_name": "Workspace URL"},
        }

    def build(
        self,
        zip_path: str,
        metadata: Optional[Dict] = None,
        workspace_url: Optional[str] = None,
    ) -> List[Document]:
        return SlackDirectoryLoader(zip_path=zip_path, metadata=metadata, workspace_url=workspace_url).load()
