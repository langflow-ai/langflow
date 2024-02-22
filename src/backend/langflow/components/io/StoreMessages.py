from typing import List, Optional

from langflow import CustomComponent
from langflow.field_typing import Text
from langflow.memory import add_messages
from langflow.schema import Record


class StoreMessages(CustomComponent):
    display_name = "Store Messages"
    description = "Used to store messages."

    def build_config(self):
        return {
            "records": {
                "display_name": "Records",
                "info": "The list of records to store. Each record should contain the keys 'sender', 'sender_name', and 'session_id'.",
            },
            "texts": {
                "display_name": "Texts",
                "info": "The list of texts to store. If records is not provided, texts must be provided.",
            },
            "session_id": {
                "display_name": "Session ID",
                "info": "The session ID to store.",
            },
            "sender": {
                "display_name": "Sender",
                "info": "The sender to store.",
            },
            "sender_name": {
                "display_name": "Sender Name",
                "info": "The sender name to store.",
            },
        }

    def build(
        self,
        records: Optional[List[Record]] = None,
        texts: Optional[List[Text]] = None,
        session_id: Optional[str] = None,
        sender: Optional[str] = None,
        sender_name: Optional[str] = None,
    ) -> List[Record]:
        # Records is the main way to store messages
        # If records is not provided, we can use texts
        # but we need to create the records from the texts
        # and the other parameters
        if not texts and not records:
            raise ValueError("Either texts or records must be provided.")

        if not records:
            records = []
            if not session_id or not sender or not sender_name:
                raise ValueError("If passing texts, session_id, sender, and sender_name must be provided.")
            for text in texts:
                record = Record(
                    text=text,
                    data={
                        "session_id": session_id,
                        "sender": sender,
                        "sender_name": sender_name,
                    },
                )
                records.append(record)
        elif isinstance(records, Record):
            records = [records]

        self.status = records
        records = add_messages(records)
        return records
