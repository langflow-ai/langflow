from langflow.interface.base import BaseFunction

DEFAULT_CONNECTOR_FUNCTION = """
def connector(text: str) -> str:
    \"\"\"This is a default python function that returns the input text\"\"\"
    return text
"""

DALL_E2_FUNCTION = """
import openai
from langflow import cache_manager
import io
import base64
import os
from PIL import Image
def create_image(prompt: str) -> str:
    openai.api_key = os.getenv("OPENAI_API_KEY")

    response = openai.Image.create(
        prompt=prompt,
        n=1,
        size="256x256",
        response_format="b64_json",
    )
    # load the image
    for image_dict in response["data"]:
        image_data = base64.b64decode(image_dict["b64_json"])
        cache_manager.add_image("image", Image.open(io.BytesIO(image_data)))
    return prompt
"""


class ConnectorFunction(BaseFunction):
    """Chain connector"""

    code: str = DEFAULT_CONNECTOR_FUNCTION


class DallE2Generator(BaseFunction):
    """DALL-E 2 Generator"""

    code: str = DALL_E2_FUNCTION


CONNECTORS = {
    "ConnectorFunction": ConnectorFunction,
    "DallE2Generator": DallE2Generator,
}
