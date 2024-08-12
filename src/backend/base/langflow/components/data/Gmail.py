import base64
import re
import json
from typing import Any, Iterator, List, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langflow.custom import Component
from langflow.inputs import MessageTextInput
from langflow.io import SecretStrInput
from langflow.template import Output
from langflow.schema import Data
from langchain_google_community.gmail.loader import GMailLoader
from langchain_core.chat_sessions import ChatSession
from langchain_core.messages import HumanMessage
from json.decoder import JSONDecodeError
from google.auth.exceptions import RefreshError


class GmailLoaderComponent(Component):
    display_name = "Gmail Loader"
    description = "Loads emails from Gmail using provided credentials."
    icon = "Google"

    inputs = [
        SecretStrInput(
            name="json_string",
            display_name="JSON String of the Service Account Token",
            info="JSON string containing OAuth 2.0 access token information for service account access",
            required=True,
            value=str("""{
                "account": "",
                "client_id": "",
                "client_secret": "",
                "expiry": "",
                "refresh_token": "",
                "scopes": [
                    "https://www.googleapis.com/auth/gmail.readonly",
                ],
                "token": "",
                "token_uri": "https://oauth2.googleapis.com/token",
                "universe_domain": "googleapis.com"
            }"""),
        ),
        MessageTextInput(
            name="label_ids",
            display_name="Label IDs",
            info="Comma-separated list of label IDs to filter emails.",
            required=True,
            value="INBOX,SENT,UNREAD,IMPORTANT",
        ),
        MessageTextInput(
            name="max_results",
            display_name="Max Results",
            info="Maximum number of emails to load.",
            required=True,
            value="10",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="load_emails"),
    ]

    def load_emails(self) -> Data:
        class CustomGMailLoader(GMailLoader):
            def __init__(
                self, creds: Any, n: int = 100, label_ids: Optional[List[str]] = None, raise_error: bool = False
            ) -> None:
                super().__init__(creds, n, raise_error)
                self.label_ids = label_ids if label_ids is not None else ["SENT"]

            def clean_message_content(self, message):
                # Remove URLs
                message = re.sub(r"http\S+|www\S+|https\S+", "", message, flags=re.MULTILINE)

                # Remove email addresses
                message = re.sub(r"\S+@\S+", "", message)

                # Remove special characters and excessive whitespace
                message = re.sub(r"[^A-Za-z0-9\s]+", " ", message)
                message = re.sub(r"\s{2,}", " ", message)

                # Trim leading and trailing whitespace
                message = message.strip()

                return message

            def _extract_email_content(self, msg: Any) -> HumanMessage:
                from_email = None
                for values in msg["payload"]["headers"]:
                    name = values["name"]
                    if name == "From":
                        from_email = values["value"]
                if from_email is None:
                    raise ValueError("From email not found.")

                if "parts" in msg["payload"]:
                    parts = msg["payload"]["parts"]
                else:
                    parts = [msg["payload"]]

                for part in parts:
                    if part["mimeType"] == "text/plain":
                        data = part["body"]["data"]
                        data = base64.urlsafe_b64decode(data).decode("utf-8")
                        pattern = re.compile(r"\r\nOn .+(\r\n)*wrote:\r\n")
                        newest_response = re.split(pattern, data)[0]
                        message = HumanMessage(
                            content=self.clean_message_content(newest_response),
                            additional_kwargs={"sender": from_email},
                        )
                        return message
                raise ValueError("No plain text part found in the email.")

            def _get_message_data(self, service: Any, message: Any) -> ChatSession:
                msg = service.users().messages().get(userId="me", id=message["id"]).execute()
                message_content = self._extract_email_content(msg)

                in_reply_to = None
                email_data = msg["payload"]["headers"]
                for values in email_data:
                    name = values["name"]
                    if name == "In-Reply-To":
                        in_reply_to = values["value"]

                thread_id = msg["threadId"]

                if in_reply_to:
                    thread = service.users().threads().get(userId="me", id=thread_id).execute()
                    messages = thread["messages"]

                    response_email = None
                    for message in messages:
                        email_data = message["payload"]["headers"]
                        for values in email_data:
                            if values["name"] == "Message-ID":
                                message_id = values["value"]
                                if message_id == in_reply_to:
                                    response_email = message
                    if response_email is None:
                        raise ValueError("Response email not found in the thread.")
                    starter_content = self._extract_email_content(response_email)
                    return ChatSession(messages=[starter_content, message_content])
                else:
                    return ChatSession(messages=[message_content])

            def lazy_load(self) -> Iterator[ChatSession]:
                service = build("gmail", "v1", credentials=self.creds)
                results = (
                    service.users().messages().list(userId="me", labelIds=self.label_ids, maxResults=self.n).execute()
                )
                messages = results.get("messages", [])
                if not messages:
                    print("No messages found with the specified labels.")
                for message in messages:
                    try:
                        yield self._get_message_data(service, message)
                    except Exception as e:
                        if self.raise_error:
                            raise e
                        else:
                            print(f"Error processing message {message['id']}: {e}")

        json_string = self.json_string
        label_ids = self.label_ids.split(",") if self.label_ids else ["INBOX"]
        max_results = int(self.max_results) if self.max_results else 100

        # Load the token information from the JSON string
        try:
            token_info = json.loads(json_string)
        except JSONDecodeError as e:
            raise ValueError("Invalid JSON string") from e

        creds = Credentials.from_authorized_user_info(token_info)

        # Initialize the custom loader with the provided credentials
        loader = CustomGMailLoader(creds=creds, n=max_results, label_ids=label_ids)

        try:
            docs = loader.load()
        except RefreshError as e:
            raise ValueError(
                "Authentication error: Unable to refresh authentication token. Please try to reauthenticate."
            ) from e
        except Exception as e:
            raise ValueError(f"Error loading documents: {e}") from e

        # Return the loaded documents
        self.status = docs
        return Data(data={"text": docs})
