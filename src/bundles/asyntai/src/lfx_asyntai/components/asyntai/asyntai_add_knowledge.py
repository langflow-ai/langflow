from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, MultilineInput, SecretStrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output
from lfx_asyntai.components.asyntai.asyntai_common import AsyntaiAPIError, asyntai_request, clean_text


class AsyntaiAddKnowledgeComponent(Component):
    """Add a web page or a text to the knowledge base of an Asyntai AI chatbot."""

    display_name = "Asyntai Add Knowledge"
    description = (
        "Add a web page or a text to the knowledge base of an Asyntai AI chatbot, "
        "so the chatbot can answer questions about it."
    )
    documentation = "https://asyntai.com/documentation/integrations/langflow/"
    icon = "book-plus"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="Page URL",
            required=False,
            info="Address of a web page to read into the knowledge base. Leave empty to add a text instead.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="title",
            display_name="Text Title",
            required=False,
            info="Title of the text, for example 'Opening hours'. Used only when Page URL is empty.",
            tool_mode=True,
        ),
        MultilineInput(
            name="content",
            display_name="Text",
            required=False,
            info="The text to add. Used only when Page URL is empty.",
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
            info="Website ID or domain of the chatbot, for example 'example.com'. "
            "Leave empty to use the primary website of the account.",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="asyntai_add_knowledge"),
    ]

    def _error(self, message: str) -> Data:
        result = Data(text=message, data={"error": message})
        self.status = result
        return result

    def asyntai_add_knowledge(self) -> Data:
        """Add the page or the text and return what Asyntai stored."""
        url = clean_text(self.url)
        title = clean_text(self.title)
        content = clean_text(self.content)
        website = clean_text(self.website)

        if url:
            path, body = "/knowledge/url/", {"url": url}
        elif content:
            path, body = "/knowledge/text/", {"title": title or content[:60], "content": content}
        else:
            return self._error("Enter a Page URL, or a Text to add to the Asyntai knowledge base.")
        if website:
            body["website_id"] = website

        try:
            payload = asyntai_request("POST", path, self.asyntai_api_key, json_body=body)
        except AsyntaiAPIError as exc:
            return self._error(str(exc))

        stored = payload.get("title") or payload.get("url") or url or title
        chunks = payload.get("chunks_created")
        summary = f"Added '{stored}' to the Asyntai knowledge base."
        if isinstance(chunks, int):
            summary = f"Added '{stored}' to the Asyntai knowledge base ({chunks} chunks)."
        result = Data(
            text=summary,
            data={
                "source": url or "text",
                "title": stored,
                "chunks_created": chunks,
            },
        )
        self.status = result
        return result
