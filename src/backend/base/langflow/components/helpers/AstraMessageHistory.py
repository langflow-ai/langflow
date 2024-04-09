from typing import List, Optional

from langchain_community.chat_message_histories import AstraDBChatMessageHistory

from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record
from langflow.services.deps import get_monitor_service


class AstraMessageHistoryComponent(CustomComponent):
    display_name = "Astra Message History"
    description = "Retrieves stored chat messages from Astra DB given a specific Session ID."
    beta: bool = True

    def build_config(self):
        return {
            "api_endpoint": {
                "display_name": "Astra DB API Endpoint",
                "info": "Astra DB API Endpoint.",
                "input_types": ["Text"],
            },
            "token": {
                "display_name": "Astra DB Application Token",
                "info": "Astra DB Application Token.",
                "input_types": ["Text"],
            },
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
        }

    def build(
        self,
        api_endpoint: Optional[str] = None,
        token: Optional[str] = None,
        sender: Optional[str] = "Machine and User",
        sender_name: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Record]:
        # Initialize the AstraDBChatMessageHistory class
        astra_messages = AstraDBChatMessageHistory(
            session_id=session_id,
            api_endpoint=api_endpoint,
            token=token,
        )

        # Get the messages
        monitor_service = get_monitor_service()

        # Get the messages from the monitor service
        messages_df = monitor_service.get_messages(
            sender=sender,
            sender_name=sender_name,
            session_id=session_id,
        )

        # Iterate over the messages
        records = []
        for row in messages_df.itertuples():
            # Store the messages
            astra_messages.add_user_message(row.message)

            record = Record(
                data={
                    "text": row.message,
                    "sender": row.sender,
                    "sender_name": row.sender_name,
                    "session_id": row.session_id,
                },
            )
            records.append(record)

        # Store the messages
        self.status = astra_messages.messages

        return astra_messages
