from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from langflow.custom import Component
from langflow.io import DropdownInput, Output
from langflow.schema.message import Message


class CurrentDateComponent(Component):
    display_name = "Current Date"
    description = "Returns the current date and time in the selected timezone."
    icon = "clock"
    beta = True
    name = "CurrentDate"

    inputs = [
        DropdownInput(
            name="timezone",
            display_name="Timezone",
            options=[
                "UTC",
                "US/Eastern",
                "US/Central",
                "US/Mountain",
                "US/Pacific",
                "Europe/London",
                "Europe/Paris",
                "Europe/Berlin",
                "Europe/Moscow",
                "Asia/Tokyo",
                "Asia/Shanghai",
                "Asia/Singapore",
                "Asia/Dubai",
                "Australia/Sydney",
                "Australia/Melbourne",
                "Pacific/Auckland",
                "America/Sao_Paulo",
                "America/Mexico_City",
                "America/Toronto",
                "America/Vancouver",
                "Africa/Cairo",
                "Africa/Johannesburg",
                "Atlantic/Reykjavik",
                "Indian/Maldives",
                "America/Bogota",
                "America/Lima",
                "America/Santiago",
                "America/Buenos_Aires",
                "America/Caracas",
                "America/La_Paz",
                "America/Montevideo",
                "America/Asuncion",
                "America/Cuiaba",
            ],
            value="UTC",
            info="Select the timezone for the current date and time.",
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
