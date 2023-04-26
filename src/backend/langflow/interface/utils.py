import base64
from io import BytesIO
import json
import os
from PIL.Image import Image
from langchain.callbacks.base import AsyncCallbackManager
from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain.llms import AzureOpenAI, OpenAI
from langflow.api.callback import StreamingLLMCallbackHandler

import yaml


def load_file_into_dict(file_path: str) -> dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == ".json":
        with open(file_path, "r") as json_file:
            data = json.load(json_file)
    elif file_extension in [".yaml", ".yml"]:
        with open(file_path, "r") as yaml_file:
            data = yaml.safe_load(yaml_file)
    else:
        raise ValueError("Unsupported file type. Please provide a JSON or YAML file.")

    return data


def pil_to_base64(image: Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue())
    return img_str.decode("utf-8")


def try_setting_streaming_options(langchain_object, websocket):
    # If the LLM type is OpenAI or ChatOpenAI,
    # set streaming to True
    # First we need to find the LLM
    llm = None
    if hasattr(langchain_object, "llm"):
        llm = langchain_object.llm
    elif hasattr(langchain_object, "llm_chain") and hasattr(
        langchain_object.llm_chain, "llm"
    ):
        llm = langchain_object.llm_chain.llm
    if isinstance(llm, (OpenAI, ChatOpenAI, AzureOpenAI, AzureChatOpenAI)):
        llm.streaming = bool(hasattr(llm, "streaming"))
        stream_handler = StreamingLLMCallbackHandler(websocket)
        stream_manager = AsyncCallbackManager([stream_handler])
        llm.callback_manager = stream_manager

    return langchain_object
