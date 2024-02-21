from typing import List

from langflow import CustomComponent
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
        }

    def build(
        self,
        records: List[Record],
    ) -> List[Record]:
        self.status = records
        records = add_messages(records)
        return records
