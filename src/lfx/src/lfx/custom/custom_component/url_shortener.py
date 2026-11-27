# from lfx.field_typing import Data
import httpx
from bs4 import BeautifulSoup

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data


class CustomComponent(Component):
    display_name = "Url Shortener"
    description = "Shortens the URL"
    documentation: str = ""
    icon = "code"
    name = "CustomComponent"

    inputs = [
        MessageTextInput(
            name="URL",
            display_name="Input Value",
            info="This is a custom component Input",
            value="kjjkj",
            tool_mode=False,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        data = Data(value=self.URL)
        self.log(f"data is {data}")
        try:
            payload = {"url": self.URL}
            resp = httpx.get("http://grambox.in/bitly/shrink/", params=payload)
            htmlContent = resp.text
            soup = BeautifulSoup(htmlContent, "html.parser")
            short_url = soup.find("h1").text.strip()
            result = Data(value=short_url)
            self.status = result
            return result
        except Exception as e:
            result = Data(value=f"Error: {e!s}")
            self.status = "failed"
            return result
        return ""
        # self.status = data
