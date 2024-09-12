import re

from langchain_community.document_loaders.web_base import WebBaseLoader

from langflow.helpers.data import data_to_text
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class URLComponent(Component):
    display_name = "URL"
    description = "Fetch content from one or more URLs."
    icon = "layout-template"
    name = "URL"

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info="Enter one or more URLs, by clicking the '+' button.",
            is_list=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="fetch_content"),
        Output(display_name="Text", name="text", method="fetch_content_text"),
    ]

    def ensure_url(self, string: str) -> str:
        """
        Ensures the given string is a URL by adding 'http://' if it doesn't start with 'http://' or 'https://'.
        Raises an error if the string is not a valid URL.

        Parameters:
            string (str): The string to be checked and possibly modified.

        Returns:
            str: The modified string that is ensured to be a URL.

        Raises:
            ValueError: If the string is not a valid URL.
        """
        if not string.startswith(("http://", "https://")):
            string = "http://" + string

        # Basic URL validation regex
        url_regex = re.compile(
            r"^(https?:\/\/)?"  # optional protocol
            r"(www\.)?"  # optional www
            r"([a-zA-Z0-9.-]+)"  # domain
            r"(\.[a-zA-Z]{2,})?"  # top-level domain
            r"(:\d+)?"  # optional port
            r"(\/[^\s]*)?$",  # optional path
            re.IGNORECASE,
        )

        if not url_regex.match(string):
            raise ValueError(f"Invalid URL: {string}")

        return string

    def fetch_content(self) -> list[Data]:
        urls = [self.ensure_url(url.strip()) for url in self.urls if url.strip()]
        loader = WebBaseLoader(web_paths=urls, encoding="utf-8")
        docs = loader.load()
        data = [Data(text=doc.page_content, **doc.metadata) for doc in docs]
        self.status = data
        return data

    def fetch_content_text(self) -> Message:
        data = self.fetch_content()

        result_string = data_to_text("{text}", data)
        self.status = result_string
        return Message(text=result_string)
