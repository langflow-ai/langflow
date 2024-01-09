
from langflow import CustomComponent
from typing import Optional, Dict

class SlackDirectoryLoaderComponent(CustomComponent):
    display_name = "SlackDirectoryLoader"
    description = "Load from a `Slack` directory dump."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/slack"

    def build_config(self):
        return {
            "zip_path": {"display_name": "Path to zip file"},
            "metadata": {"display_name": "Metadata"},
            "workspace_url": {"display_name": "Workspace URL"},
        }

    def build(
        self,
        zip_path: str,
        metadata: Optional[Dict] = None,
        workspace_url: Optional[str] = None,
    ) -> 'Document':
        # Assuming there is a SlackDirectoryLoader class that takes these parameters
        # Since the actual implementation details are not provided, this is a placeholder
        # Replace SlackDirectoryLoader with the actual class that should be instantiated
        return SlackDirectoryLoader(zip_path=zip_path, metadata=metadata, workspace_url=workspace_url)
