import json
import os

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data


class PlivoSendSMSComponent(Component):
    display_name = "Plivo Send SMS"
    description = "Send an SMS message through the Plivo Messaging API."
    documentation: str = "https://www.plivo.com/docs/messaging/api/messages"
    icon = "Plivo"
    name = "PlivoSendSMSComponent"

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
            name="src",
            display_name="From Number",
            info="Sender ID: a Plivo phone number, short code, or alphanumeric sender ID in E.164 format.",
            value=os.getenv("PLIVO_SRC", ""),
            required=True,
        ),
        MessageTextInput(
            name="dst",
            display_name="To Number",
            info="Recipient in E.164 format. Multiple recipients are joined with '<'.",
            value="",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="text",
            display_name="Message",
            info="The message body to send.",
            value="",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        try:
            auth_id = self.auth_id.strip()
            payload = {
                "src": self.src.strip(),
                "dst": self.dst.strip(),
                "text": self.text,
                "type": "sms",
            }

            url = f"https://api.plivo.com/v1/Account/{auth_id}/Message/"

            await logger.ainfo("Sending Plivo SMS with payload: %s", payload)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    auth=(auth_id, self.auth_token.strip()),
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                response_data = response.json()
                await logger.ainfo("Plivo SMS queued: %s", response_data)

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
