from typing import List, Optional
from langflow import CustomComponent
from langflow.services.getters import get_monitor_service


class SessionIDComponent(CustomComponent):
    display_name = "Session ID"
    description = "Used to retrieve the session ID."

    def build_config(self):
        monitor_service = get_monitor_service()
        chat_history_df = monitor_service.to_df("messages")
        options = chat_history_df["session_id"].unique().tolist()
        return {
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "options": options or [""],
                "value": options[0] if options else None,
            },
            "new_session_id": {
                "display_name": "New Session ID",
                "info": "New Session ID to be used.",
            },
        }

    def build(
        self,
        new_session_id: Optional[str] = None,
        session_id: Optional[List[str]] = None,
    ) -> str:
        if not new_session_id and not session_id:
            raise ValueError("Either New Session ID or Session ID must be provided.")
        # If new_session_id is provided, we return it
        # If not, we return session_id
        return new_session_id or session_id
