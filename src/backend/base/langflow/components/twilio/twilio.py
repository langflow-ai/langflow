from base64 import b64encode

import httpx

from langflow.custom import Component
from langflow.inputs.inputs import MultilineInput
from langflow.io import Output, SecretStrInput, StrInput


class TwilioComponent(Component):
    display_name = "Twilio SMS"
    description = "Uses the Twilio REST API to send an SMS message."
    documentation = (
        "https://python.langchain.com/api_reference/unstructured/document_loaders/"
        "langchain_unstructured.document_loaders.UnstructuredLoader.html"
    )
    name = "Twilio"

    inputs = [
        StrInput(
            name="account_sid",
            display_name="Account SID",
            info="Your Twilio Account SID",
        ),
        SecretStrInput(
            name="auth_token",
            display_name="Auth Token",
            info="Your Twilio Auth Token",
        ),
        StrInput(
            name="twilio_number",
            display_name="Twilio Phone Number",
            info="The phone number to send the SMS from.",
        ),
        StrInput(
            name="recipient_number",
            display_name="Recipient Phone Number",
            info="The phone number to send the SMS to.",
        ),
        MultilineInput(
            name="message",
            display_name="Message",
            info="The content of the SMS message.",
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="send_twilio_sms"),
    ]

    def send_twilio_sms(self) -> str | None:
        """Send a text message using Twilio's REST API with httpx.

        Args:
            to_number (str): The recipient's phone number (e.g., '+1234567890').
            message (str): The text message content.

        Returns:
            dict: The response from Twilio's API.

        """
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        headers = {"Authorization": "Basic " + b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()}
        data = {
            "From": self.twilio_number,
            "To": self.recipient_number,
            "Body": self.message,
        }

        try:
            response = httpx.post(url, headers=headers, data=data)
            response.raise_for_status()

            self.log(f"Message sent successfully! SID: {response.json().get('sid')}")

            return response.json()
        except httpx.HTTPStatusError as e:
            self.log(f"Failed to send message: {e.response.text}")

            return e.response.json()
        except Exception as e:  # noqa: BLE001
            self.log(f"An error occurred: {e}")

            return None
