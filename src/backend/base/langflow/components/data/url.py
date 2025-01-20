import re

from langchain_community.document_loaders import AsyncHtmlLoader, WebBaseLoader

from langflow.custom import Component
from langflow.helpers.data import data_to_text
from langflow.io import DropdownInput, MessageTextInput, Output
from langflow.schema import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message


class URLComponent(Component):
    display_name = "URL"
    description = "Load and retrive data from specified URLs."
    icon = "layout-template"
    name = "URL"

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            is_list=True,
            tool_mode=True,
            placeholder="Enter a URL...",
            list_add_label="Add URL",
        ),
        DropdownInput(
            name="format",
            display_name="Output Format",
            info="Output Format. Use 'Text' to extract the text from the HTML or 'Raw HTML' for the raw HTML content.",
            options=["Text", "Raw HTML"],
            value="Text",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="fetch_content"),
        Output(display_name="Message", name="text", method="fetch_content_text"),
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    def ensure_url(self, string: str) -> str:
        """Ensures the given string is a URL by adding 'http://' if it doesn't start with 'http://' or 'https://'.

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
            msg = f"Invalid URL: {string}"
            raise ValueError(msg)

        return string

    def fetch_content(self) -> list[Data]:
        urls = [self.ensure_url(url.strip()) for url in self.urls if url.strip()]
        if self.format == "Raw HTML":
            loader = AsyncHtmlLoader(web_path=urls, encoding="utf-8")
        else:
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

    def as_dataframe(self) -> DataFrame:
        return DataFrame(self.fetch_content())
