import json
import os

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data


class PlivoLookupNumberComponent(Component):
    display_name = "Plivo Lookup Number"
    description = "Look up carrier and formatting details for a phone number through the Plivo Lookup API."
    documentation: str = "https://www.plivo.com/docs/lookup/api/number"
    icon = "Plivo"
    name = "PlivoLookupNumberComponent"

    inputs = [
        SecretStrInput(
            name="auth_id",
            display_name="Plivo Auth ID",
            info="Your Plivo Auth ID from the console at cx.plivo.com.",
            value=os.getenv("PLIVO_AUTH_ID", ""),
            required=True,
        ),
        SecretStrInput(
            name="auth_token",
            display_name="Plivo Auth Token",
            info="Your Plivo Auth Token from the console at cx.plivo.com.",
            value=os.getenv("PLIVO_AUTH_TOKEN", ""),
            required=True,
        ),
        MessageTextInput(
            name="number",
            display_name="Phone Number",
            info="The phone number to look up, in E.164 format such as +14155551234.",
            value="",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="type",
            display_name="Lookup Type",
            info=(
                "Choose 'carrier' to include carrier name and line type. Choose 'none' for country and formatting only."
            ),
            options=["carrier", "none"],
            value="carrier",
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        try:
            auth_id = self.auth_id.strip()
            number = self.number.strip()
            url = f"https://lookup.plivo.com/v1/Number/{number}"
            params = {} if self.type == "none" else {"type": self.type}

            await logger.ainfo("Looking up Plivo number: %s", number)

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    auth=(auth_id, self.auth_token.strip()),
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                response_data = response.json()
                await logger.ainfo("Plivo lookup result: %s", response_data)

        except httpx.HTTPStatusError as http_err:
            await logger.aexception("HTTP error occurred")
            response_data = {"error": f"HTTP error occurred: {http_err}", "response_text": response.text}
        except httpx.RequestError as req_err:
            await logger.aexception("Request failed")
            response_data = {"error": f"Request failed: {req_err}"}
        except json.JSONDecodeError as json_err:
            await logger.aexception("Response parsing failed")
            response_data = {"error": f"Response parsing failed: {json_err}", "raw_response": response.text}
        except Exception as e:  # noqa: BLE001
            await logger.aexception("An unexpected error occurred")
            response_data = {"error": f"An unexpected error occurred: {e!s}"}

        self.status = response_data
        return Data(value=response_data)
