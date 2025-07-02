from langflow.base.composio.composio_base import ComposioBaseComponent
from loguru import logger

class ComposioGmailAPIComponent(ComposioBaseComponent):
    display_name: str = "Gmail"
    icon = "Google"
    documentation: str = "https://docs.composio.dev"
    app_name = "gmail"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.post_processors = {
            "GMAIL_SEND_EMAIL": self._process_send_email_response,
            "GMAIL_FETCH_EMAILS": self._process_fetch_emails_response,
        }

    def _process_send_email_response(self, raw_data):
        """Post-processor for GMAIL_SEND_EMAIL action."""
        if isinstance(raw_data, dict):
            response_data = raw_data.get("response_data", raw_data)
            
            return {
                "message_id": response_data.get("id"),
                "thread_id": response_data.get("threadId"),
                "label_ids": response_data.get("labelIds", []),
            }
        return raw_data

    def _process_fetch_emails_response(self, raw_data):
        """Post-processor for GMAIL_FETCH_EMAILS action."""
        if isinstance(raw_data, dict):
            messages = raw_data.get("messages", [])
            if messages:
                return messages
        return raw_data

    def set_default_tools(self):
        """Set the default tools for Gmail component."""
