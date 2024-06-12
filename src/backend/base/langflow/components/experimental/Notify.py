from typing import Optional

from langflow.custom import CustomComponent
from langflow.schema import Data


class NotifyComponent(CustomComponent):
    display_name = "Notify"
    description = "A component to generate a notification to Get Notified component."
    icon = "Notify"
    beta: bool = True

    def build_config(self):
        return {
            "name": {"display_name": "Name", "info": "The name of the notification."},
            "record": {"display_name": "Data", "info": "The record to store."},
            "append": {
                "display_name": "Append",
                "info": "If True, the record will be appended to the notification.",
            },
        }

    def build(self, name: str, record: Optional[Data] = None, append: bool = False) -> Data:
        if record and not isinstance(record, Data):
            if isinstance(record, str):
                record = Data(text=record)
            elif isinstance(record, dict):
                record = Data(data=record)
            else:
                record = Data(text=str(record))
        elif not record:
            record = Data(text="")
        if record:
            if append:
                self.append_state(name, record)
            else:
                self.update_state(name, record)
        else:
            self.status = "No record provided."
        self.status = record
        return record
