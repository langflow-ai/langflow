import json
from pathlib import Path
from string import Formatter

import yaml

from lfx.services.deps import get_settings_service


def extract_input_variables_from_prompt(prompt: str) -> list[str]:
    """Extract variable names from a prompt string using Python's built-in string formatter.

    Uses the same convention as Python's .format() method:
    - Single braces {name} are variable placeholders
    - Double braces {{name}} are escape sequences that render as literal {name}.
    """
    formatter = Formatter()
    variables: list[str] = []
    seen: set[str] = set()
    # Use local bindings for micro-optimization
    variables_append = variables.append
    seen_add = seen.add
    seen_contains = seen.__contains__
    for _, field_name, _, _ in formatter.parse(prompt):
        if field_name and not seen_contains(field_name):
            variables_append(field_name)
            seen_add(field_name)
    return variables


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
            msg = f"Error loading file {file_path}: {exc}"
            raise ValueError(msg) from exc

    return data


def build_langfuse_url(trace_id: str):
    """Build the URL to the Langfuse trace."""
    if not trace_id:
        return ""

    settings_service = get_settings_service()
    langfuse_host = settings_service.settings.LANGFUSE_HOST
    return f"{langfuse_host}/trace/{trace_id}"


def build_langsmith_url(run_id: str):
    """Build the URL to the LangSmith run."""
    if not run_id:
        return ""
    return f"https://smith.langchain.com/runs/{run_id}"


def build_flow_url(session_id: str, flow_id: str):
    """Build the URL to the flow."""
    if not session_id or not flow_id:
        return ""

    settings_service = get_settings_service()
    frontend_url = getattr(settings_service.settings, "FRONTEND_URL", "http://localhost:3000")
    return f"{frontend_url}/flows/{flow_id}?sessionId={session_id}"


def pil_to_base64(image) -> str:
    """Convert PIL Image to base64 string."""
    import base64
    from io import BytesIO

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue())
    return img_str.decode("utf-8")


def try_setting_streaming_options(langchain_object):
    """Try setting streaming options on LangChain objects."""
    from langchain_core.language_models import BaseLanguageModel

    # Import chat config - we'll need to create this module
    try:
        from lfx.services.chat.config import ChatConfig

        streaming = ChatConfig.streaming
    except ImportError:
        streaming = False

    # If the LLM type is OpenAI or ChatOpenAI, set streaming to True
    # First we need to find the LLM
    llm = None
    if hasattr(langchain_object, "llm"):
        llm = langchain_object.llm
    elif hasattr(langchain_object, "llm_chain") and hasattr(langchain_object.llm_chain, "llm"):
        llm = langchain_object.llm_chain.llm

    if isinstance(llm, BaseLanguageModel):
        if hasattr(llm, "streaming") and isinstance(llm.streaming, bool):
            llm.streaming = streaming
        elif hasattr(llm, "stream") and isinstance(llm.stream, bool):
            llm.stream = streaming

    return langchain_object


def setup_llm_caching() -> None:
    """Setup LLM caching."""
    from loguru import logger

    settings_service = get_settings_service()
    try:
        set_langchain_cache(settings_service.settings)
    except ImportError:
        logger.warning(f"Could not import {getattr(settings_service.settings, 'cache_type', 'cache')}. ")
    except Exception:  # noqa: BLE001
        logger.warning("Could not setup LLM caching.")


def set_langchain_cache(settings) -> None:
    """Set LangChain cache using settings."""
    import os

    from langchain.globals import set_llm_cache
    from loguru import logger

    from lfx.interface.importing.utils import import_class

    if cache_type := os.getenv("LANGFLOW_LANGCHAIN_CACHE"):
        try:
            cache_class = import_class(
                f"langchain_community.cache.{cache_type or getattr(settings, 'LANGCHAIN_CACHE', '')}"
            )

            logger.debug(f"Setting up LLM caching with {cache_class.__name__}")
            set_llm_cache(cache_class())
            logger.info(f"LLM caching setup with {cache_class.__name__}")
        except ImportError:
            logger.warning(f"Could not import {cache_type}. ")
    else:
        logger.debug("No LLM cache set.")
