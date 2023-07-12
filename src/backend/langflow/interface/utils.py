import base64
import json
import os
from io import BytesIO
import re


import yaml
from langchain.base_language import BaseLanguageModel
from PIL.Image import Image
from langflow.utils.logger import logger
from langflow.chat.config import ChatConfig


def load_file_into_dict(file_path: str) -> dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Files names are UUID, so we can't find the extension
    with open(file_path, "r") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            file.seek(0)
            data = yaml.safe_load(file)
        except ValueError as exc:
            raise ValueError("Invalid file type. Expected .json or .yaml.") from exc
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

    if isinstance(llm, BaseLanguageModel):
        if hasattr(llm, "streaming") and isinstance(llm.streaming, bool):
            llm.streaming = ChatConfig.streaming
        elif hasattr(llm, "stream") and isinstance(llm.stream, bool):
            llm.stream = ChatConfig.streaming

    return langchain_object


def extract_input_variables_from_prompt(prompt: str) -> list[str]:
    """Extract input variables from prompt."""
    return re.findall(r"{(.*?)}", prompt)


def setup_llm_caching():
    """Setup LLM caching."""

    from langflow.settings import settings

    try:
        set_langchain_cache(settings)
    except ImportError:
        logger.warning(f"Could not import {settings.cache}. ")
    except Exception as exc:
        logger.warning(f"Could not setup LLM caching. Error: {exc}")


# TODO Rename this here and in `setup_llm_caching`
def set_langchain_cache(settings):
    import langchain
    from langflow.interface.importing.utils import import_class

    cache_type = os.getenv("LANGFLOW_LANGCHAIN_CACHE")
    cache_class = import_class(f"langchain.cache.{cache_type or settings.cache}")

    logger.debug(f"Setting up LLM caching with {cache_class.__name__}")
    langchain.llm_cache = cache_class()
    logger.info(f"LLM caching setup with {cache_class.__name__}")
