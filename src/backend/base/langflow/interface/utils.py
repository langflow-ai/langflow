import base64
import json
import os
import re
from io import BytesIO
from pathlib import Path

import yaml
from langchain_core.language_models import BaseLanguageModel
from loguru import logger
from PIL.Image import Image

from langflow.services.chat.config import ChatConfig
from langflow.services.deps import get_settings_service


def load_file_into_dict(file_path: str) -> dict:
    file_path_ = Path(file_path)
    if not file_path_.exists():
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)

    # Files names are UUID, so we can't find the extension
    with file_path_.open(encoding="utf-8") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            file.seek(0)
            data = yaml.safe_load(file)
        except ValueError as exc:
            msg = "Invalid file type. Expected .json or .yaml."
            raise ValueError(msg) from exc
    return data


def pil_to_base64(image: Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue())
    return img_str.decode("utf-8")


def try_setting_streaming_options(langchain_object):
    # If the LLM type is OpenAI or ChatOpenAI,
    # set streaming to True
    # First we need to find the LLM
    llm = None
    if hasattr(langchain_object, "llm"):
        llm = langchain_object.llm
    elif hasattr(langchain_object, "llm_chain") and hasattr(langchain_object.llm_chain, "llm"):
        llm = langchain_object.llm_chain.llm

    if isinstance(llm, BaseLanguageModel):
        if hasattr(llm, "streaming") and isinstance(llm.streaming, bool):
            llm.streaming = ChatConfig.streaming
        elif hasattr(llm, "stream") and isinstance(llm.stream, bool):
            llm.stream = ChatConfig.streaming

    return langchain_object

def extract_input_variables_from_prompt(prompt: str) -> list[str]:
    """Extract variable names from a prompt string using single braces for variables and double braces for escaping."""
    variables: list[str] = []

    # one or more '{',   the identifier,   one or more '}'
    brace_pattern = re.compile(r"(\{+)([^{}]+?)(\}+)")

    seen: set[str] = set()

    for m in brace_pattern.finditer(prompt):
        open_run, var_name, close_run = m.groups()

        # "real" variable only when both sides have the same *odd* length
        if len(open_run) == len(close_run) and len(open_run) % 2 == 1:
            clean_name = var_name.strip()
            if clean_name not in seen:  # avoid duplicates
                variables.append(clean_name)
                seen.add(clean_name)

    return variables


def setup_llm_caching() -> None:
    """Setup LLM caching."""
    settings_service = get_settings_service()
    try:
        set_langchain_cache(settings_service.settings)
    except ImportError:
        logger.warning(f"Could not import {settings_service.settings.cache_type}. ")
    except Exception:  # noqa: BLE001
        logger.warning("Could not setup LLM caching.")


def set_langchain_cache(settings) -> None:
    from langchain.globals import set_llm_cache

    from langflow.interface.importing.utils import import_class

    if cache_type := os.getenv("LANGFLOW_LANGCHAIN_CACHE"):
        try:
            cache_class = import_class(f"langchain_community.cache.{cache_type or settings.LANGCHAIN_CACHE}")

            logger.debug(f"Setting up LLM caching with {cache_class.__name__}")
            set_llm_cache(cache_class())
            logger.info(f"LLM caching setup with {cache_class.__name__}")
        except ImportError:
            logger.warning(f"Could not import {cache_type}. ")
    else:
        logger.debug("No LLM cache set.")
