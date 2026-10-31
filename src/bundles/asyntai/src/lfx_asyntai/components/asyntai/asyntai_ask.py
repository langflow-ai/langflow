from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.message import Message
from lfx.template.field.base import Output
from lfx_asyntai.components.asyntai.asyntai_common import AsyntaiAPIError, asyntai_request, clean_text


class AsyntaiAskComponent(Component):
    """Ask the Asyntai AI chatbot a question about a website."""

    display_name = "Asyntai AI Chatbot"
    description = (
        "Ask the Asyntai AI chatbot a question. It answers from the website and knowledge base "
        "that the chatbot was set up with."
    )
    documentation = "https://asyntai.com/documentation/integrations/langflow/"
    icon = "MessagesSquare"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Question",
            required=True,
            info="The question to ask, in plain language.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="asyntai_api_key",
            display_name="Asyntai API Key",
            required=True,
            info="Your Asyntai API key. Create one in the Asyntai dashboard under Settings -> API.",
            password=True,
        ),
        MessageTextInput(
            name="website",
            display_name="Website",
            required=False,
            advanced=True,
            info="Website ID or domain of the chatbot to ask, for example 'example.com'. "
            "Leave empty to use the primary website of the account.",
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            required=False,
            advanced=True,
            info="Optional ID that keeps several questions in one conversation.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.
        Output(display_name="Answer", name="answer", method="asyntai_ask_website"),
    ]

    def _request_body(self) -> dict:
        body: dict = {"message": clean_text(self.input_value)}
        website = clean_text(self.website)
        if website:
            body["website_id"] = website
        session_id = clean_text(self.session_id)
        if session_id:
            body["session_id"] = session_id
        return body

    def asyntai_ask_website(self) -> Message:
        """Send the question to the Asyntai chat API and return the answer."""
        body = self._request_body()
        if not body["message"]:
            text = "Enter a question to ask the Asyntai AI chatbot."
        else:
            try:
                payload = asyntai_request("POST", "/chat/", self.asyntai_api_key, json_body=body)
                text = str(payload.get("response") or "")
            except AsyntaiAPIError as exc:
                text = str(exc)
        message = Message(text=text)
        self.status = text
        return message
