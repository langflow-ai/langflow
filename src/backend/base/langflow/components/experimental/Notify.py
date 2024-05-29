from typing import Optional

from langflow.custom import CustomComponent
from langflow.schema import Record


class NotifyComponent(CustomComponent):
    display_name = "Notify"
    description = "A component to generate a notification to Get Notified component."
    icon = "Notify"
    beta: bool = True

    def build_config(self):
        return {
            "name": {"display_name": "Name", "info": "The name of the notification."},
            "record": {"display_name": "Record", "info": "The record to store."},
            "append": {
                "display_name": "Append",
                "info": "If True, the record will be appended to the notification.",
            },
        }

    def build(self, name: str, record: Optional[Record] = None, append: bool = False) -> Record:
        if record and not isinstance(record, Record):
            if isinstance(record, str):
                record = Record(text=record)
            elif isinstance(record, dict):
                record = Record(data=record)
            else:
                record = Record(text=str(record))
        elif not record:
            record = Record(text="")
        if record:
            if append:
                self.append_state(name, record)
            else:
                self.update_state(name, record)
        else:
            self.status = "No record provided."
        self.status = record
        return record
