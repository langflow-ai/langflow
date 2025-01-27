import json

import requests

from langflow.base.curl.parse import parse_context
from langflow.custom import Component
from langflow.io import IntInput, MessageTextInput, Output, Message
from langflow.schema import Data


class HttpRequestTool(Component):
    display_name = "API Request Tool"
    description = "Replace your description tool for example: saber el precio de un producto por su id"
    icon = "Globe"
    name = "APIRequestTool"

    inputs = [
        MessageTextInput(
            name="curl",
            display_name="cURL",
            info="Paste a curl command to populate the fields.",
            value=(
                "write your curl for example: "
                "curl --location 'https://host/todos' "
                "--header 'some-header: some-value' "
                "--header 'Content-Type: application/json' "
                "--data '{\"product_id\": \"{product_id}\"}'"
            ),
            tool_mode=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            value=5,
            info="The timeout to use for the request.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="make_request"),
    ]

    def make_request(self) -> Data:
        curl = self.curl
        context = parse_context(curl)
        url = context.url
        method = context.method.upper()
        headers = context.headers
        body = context.data
        if "--data" in curl:
            method = "POST"

        methods = {"GET": requests.get, "POST": requests.post, "PUT": requests.put, "PATCH": requests.patch}

        request_function = methods.get(method, requests.get)
        response = request_function(
            url,
            headers=headers,
            json=body if method in {"POST", "PUT", "PATCH"} else None,
            timeout=self.timeout,
        )

        result = {
            "status_code": response.status_code,
            "data": response.json()
            if "application/json" in response.headers.get("Content-Type", "")
            else response.text,
        }

        return Message(text=json.dumps(result, indent=4))
