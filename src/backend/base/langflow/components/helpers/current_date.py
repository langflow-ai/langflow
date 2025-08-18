from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

from loguru import logger

from langflow.custom.custom_component.component import Component
from langflow.io import DropdownInput, Output
from langflow.schema.message import Message


class CurrentDateComponent(Component):
    display_name = "Current Date"
    description = "Returns the current date and time in the selected timezone."
    documentation: str = "https://docs.langflow.org/components-helpers#current-date"
    icon = "clock"
    name = "CurrentDate"

    inputs = [
        DropdownInput(
            name="timezone",
            display_name="Timezone",
            options=list(available_timezones()),
            value="UTC",
            info="Select the timezone for the current date and time.",
            tool_mode=True,
        ),
    ]
    outputs = [
        Output(display_name="Current Date", name="current_date", method="get_current_date"),
    ]

    def get_current_date(self) -> Message:
        try:
            tz = ZoneInfo(self.timezone)
            current_date = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
            result = f"Current date and time in {self.timezone}: {current_date}"
            self.status = result
            return Message(text=result)
        except Exception as e:  # noqa: BLE001
            logger.opt(exception=True).debug("Error getting current date")
            error_message = f"Error: {e}"
            self.status = error_message
            return Message(text=error_message)
