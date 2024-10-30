import base64
import json
from pathlib import Path

import requests

from langflow.custom import Component
from langflow.io import (
    FileInput,
    MessageTextInput,
    MultilineInput,
    Output,
)
from langflow.schema import Data


class OllamaImageDescription(Component):
    """This component retrieves an image description using Ollama's Large Language Model (LLM)."""

    display_name = "Ollama Image Description"
    description = "Gets image description using Ollama"

    icon = "image"
    name = "OllamaImageDescription"

    # Define the input parameters for the component
    inputs = [
        FileInput(name="image_file", display_name="Image File", file_types=["jpg", "jpeg"]),
        MultilineInput(name="content", display_name="Image Prompt", value=""),
        MessageTextInput(
            name="model",
            display_name="Model",
            value="llava:13b",
        ),
        MessageTextInput(
            name="base_url",
            display_name="LLM Base URL",
            value="http://localhost:11434",
        ),
        MessageTextInput(name="chat_path", display_name="Chat Path", value="/api/chat", advanced=True),
    ]

    # Define the output parameters for the component
    outputs = [
        Output(
            display_name="Data",
            name="data",
            method="build_output",
        ),
    ]

    def build_output(self) -> Data:
        """This method builds the output for the component.

        Returns:
            Data: The image description retrieved from the Ollama LLM.
        """
        # Get the input parameters
        image_file = self.image_file
        content = self.content
        model = self.model
        base_url = self.base_url
        chat_path = self.chat_path

        # Try to read the image file
        try:
            # with Path.open(image_file, "rb") as file:
            with Path(image_file).open("rb") as file:
                image_data = file.read()
        except FileNotFoundError:
            # Handle the case where the image file is not found
            error_message = f"Image file not found: {image_file}"
            data = Data(value=error_message)
            self.status = data
            return data

        # Encode the image data using base64
        encode_image = base64.b64encode(image_data).decode("utf-8")

        # Construct the URL and payload for the request to the Ollama LLM
        url = f"{base_url}{chat_path}"
        payload = json.dumps(
            {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                        "images": [encode_image],
                    }
                ],
                "stream": False,
            }
        )
        headers = {"Content-Type": "application/json"}

        # Try to send the request to the Ollama LLM
        try:
            response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes
        except requests.exceptions.RequestException as e:
            # Handle any exceptions that occur while sending the request
            error_message = f"Error sending request to LLM server: {e}"
            data = Data(value=error_message)
            self.status = data
            return data

        # Try to parse the response from the Ollama LLM
        try:
            response_json = json.loads(response.text)
        except json.JSONDecodeError as e:
            # Handle any exceptions that occur while parsing the response
            error_message = f"Error parsing JSON response from LLM server: {e}"
            data = Data(value=error_message)
            self.status = data
            return data

        # Try to extract the image description from the response
        try:
            image_description = response_json["message"]["content"]
        except KeyError:
            # Handle the case where the response is invalid
            error_message = "Invalid response from LLM server"
            data = Data(value=error_message)
            self.status = data
            return data

        # Return the image description
        data = Data(value=image_description)
        self.status = data
        return data
