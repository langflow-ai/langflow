import json
import re

from langchain_community.document_loaders import AsyncHtmlLoader, WebBaseLoader

from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, MessageTextInput, Output, StrInput
from langflow.schema import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message


class URLComponent(Component):
    display_name = "URL"
    description = "Load and retrieve data from specified URLs. Supports output in plain text, raw HTML, or JSON, with options for cleaning and separating multiple outputs."
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
            info="Output Format. Use 'Text' to extract text from the HTML, 'Raw HTML' for the raw HTML content, or 'JSON' to extract JSON from the HTML.",
            options=["Text", "Raw HTML", "JSON"],
            value="Text",
            real_time_refresh=True,
        ),
        StrInput(
            name="separator",
            display_name="Separator",
            value="\n\n",
            show=True,
            info="Specify the separator to use between multiple outputs. Default for Text is '\\n\\n'. Default for Raw HTML is '\\n<!-- Separator -->\\n'.",
        ),
        BoolInput(
            name="clean_extra_whitespace",
            display_name="Clean Extra Whitespace",
            value=True,
            show=True,
            info="Whether to clean excessive blank lines in the text output. Only applies to 'Text' format.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="fetch_content"),
        Output(display_name="Text", name="text", method="fetch_content_text"),
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Dynamically update fields based on selected format."""
        if field_name == "format":
            is_text_mode = field_value == "Text"
            is_json_mode = field_value == "JSON"
            build_config["separator"]["value"] = "\n\n" if is_text_mode else "\n<!-- Separator -->\n"
            build_config["clean_extra_whitespace"]["show"] = is_text_mode
            build_config["separator"]["show"] = not is_json_mode
        return build_config

    def ensure_url(self, string: str) -> str:
        """Ensures the given string is a valid URL."""
        if not string.startswith(("http://", "https://")):
            string = "http://" + string

        if not self.url_regex.match(string):
            raise ValueError(f"Invalid URL: {string}")

        if self.format == "JSON" and ".json" not in string:
            raise ValueError(f"Invalid JSON URL: {string}")

        return string

    def fetch_content(self) -> list[Data]:
        """Fetch content based on selected format."""
        urls = list({self.ensure_url(url.strip()) for url in self.urls if url.strip()})
        if not urls:
            raise ValueError("No valid URLs provided.")

        if self.format == "Raw HTML":
            loader = AsyncHtmlLoader(web_path=urls, encoding="utf-8")
        else:
            loader = WebBaseLoader(web_paths=urls, encoding="utf-8")

        docs = loader.load()

        if self.format == "JSON":
            data = []
            for doc in docs:
                try:
                    json_content = json.loads(doc.page_content)
                    data_dict = {"text": json.dumps(json_content, indent=2), **json_content, **doc.metadata}
                    data.append(Data(**data_dict))
                except json.JSONDecodeError as err:
                    raise ValueError(f"Invalid JSON content from {doc.metadata.get('source', 'unknown URL')}") from err
            return data

        return [Data(text=doc.page_content, **doc.metadata) for doc in docs]

    def fetch_content_text(self) -> Message:
        """Fetch content and return as formatted text."""
        data = self.fetch_content()

        if self.format == "JSON":
            text_list = [item.text for item in data]
            result = "\n".join(text_list)
        else:
            text_list = [item.text for item in data]
            if self.format == "Text" and self.clean_extra_whitespace:
                text_list = [re.sub(r"\n{3,}", "\n\n", text) for text in text_list]
            result = self.separator.join(text_list)

        self.status = result
        return Message(text=result)

    def as_dataframe(self) -> DataFrame:
        """Return fetched content as a DataFrame."""
        return DataFrame(self.fetch_content())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url_regex = re.compile(
            r"^(https?:\/\/)?"
            r"(www\.)?"
            r"([a-zA-Z0-9.-]+)"
            r"(\.[a-zA-Z]{2,})?"
            r"(:\d+)?"
            r"(\/[^\s]*)?$",
            re.IGNORECASE,
        )
