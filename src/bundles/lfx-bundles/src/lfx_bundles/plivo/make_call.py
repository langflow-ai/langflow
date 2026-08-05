import json
import os

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data


class PlivoMakeCallComponent(Component):
    display_name = "Plivo Make Call"
    description = "Place an outbound phone call through the Plivo Voice API."
    documentation: str = "https://www.plivo.com/docs/voice/api/call"
    icon = "Plivo"
    name = "PlivoMakeCallComponent"

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
            name="from_number",
            display_name="From Number",
            info="Caller ID: a Plivo phone number in E.164 format.",
            value=os.getenv("PLIVO_SRC", ""),
            required=True,
        ),
        MessageTextInput(
            name="to_number",
            display_name="To Number",
            info="The recipient's phone number in E.164 format.",
            value="",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="answer_url",
            display_name="Answer URL",
            info=(
                "URL Plivo fetches for call-flow XML when the call is answered. A default static URL is "
                "provided, so a basic call needs no setup. Override it with your own webhook to customize "
                "what the call says."
            ),
            value="https://s3.amazonaws.com/static.plivo.com/answer.xml",
            required=False,
        ),
        DropdownInput(
            name="answer_method",
            display_name="Answer Method",
            info=(
                "HTTP method Plivo uses to fetch the Answer URL. The built-in default Answer URL is a static "
                "file that only supports GET, so keep this on GET unless you point Answer URL at your own "
                "webhook that expects POST."
            ),
            options=["GET", "POST"],
            value="GET",
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        try:
            auth_id = self.auth_id.strip()
            payload = {
                "from": self.from_number.strip(),
                "to": self.to_number.strip(),
                "answer_url": self.answer_url.strip(),
                "answer_method": (self.answer_method or "GET").strip().upper(),
            }

            url = f"https://api.plivo.com/v1/Account/{auth_id}/Call/"

            await logger.ainfo("Placing Plivo call with payload: %s", payload)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    auth=(auth_id, self.auth_token.strip()),
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                response_data = response.json()
                await logger.ainfo("Plivo call fired: %s", response_data)

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
