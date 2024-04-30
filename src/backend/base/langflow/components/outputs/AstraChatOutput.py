from typing import Optional, Union

from langflow.base.io.astra_chat import AstraDBChatComponent
from langflow.field_typing import Text
from langflow.schema import Record


class AstraChatOutput(AstraDBChatComponent):
    display_name = "Astra DB Chat Output"
    description = "Display an Astra DB chat message in the Interaction Panel."
    icon = "ChatOutput"

    def build(
        self,
        sender: Optional[str] = "Machine",
        sender_name: Optional[str] = "AI",
        input_value: Optional[str] = None,
        session_id: Optional[str] = None,
        return_record: Optional[bool] = False,
        record_template: Optional[str] = "{text}",
    ) -> Union[Text, Record]:
        return super().build(
            sender=sender,
            sender_name=sender_name,
            input_value=input_value,
            session_id=session_id,
            return_record=return_record,
            record_template=record_template,
        )
