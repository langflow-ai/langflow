import importlib
import inspect
import json
import os
import pkgutil
import threading
import uuid
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Any

import astra_assistants.tools as astra_assistants_tools
import requests
from astra_assistants import OpenAIWithDefaultKey, patch
from astra_assistants.tools.tool_interface import ToolInterface
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from requests.exceptions import RequestException

from langflow.components.tools.mcp_stdio import create_input_schema_from_json_schema
from langflow.services.cache.utils import CacheMiss

client_lock = threading.Lock()
client = None


def get_patched_openai_client(shared_component_cache):
    os.environ["ASTRA_ASSISTANTS_QUIET"] = "true"
    client = shared_component_cache.get("client")
    if isinstance(client, CacheMiss):
        client = patch(OpenAIWithDefaultKey())
        shared_component_cache.set("client", client)
    return client


url = "https://raw.githubusercontent.com/BerriAI/litellm/refs/heads/main/model_prices_and_context_window.json"
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = json.loads(response.text)
except RequestException:
    data = {}
except JSONDecodeError:
    data = {}

# Extract the model names into a Python list
litellm_model_names = [model for model in data if model != "sample_spec"]


# To store the class names that extend ToolInterface
tool_names = []
tools_and_names = {}


def tools_from_package(your_package) -> None:
    # Iterate over all modules in the package
    package_name = your_package.__name__
    for module_info in pkgutil.iter_modules(your_package.__path__):
        module_name = f"{package_name}.{module_info.name}"

        # Dynamically import the module
        module = importlib.import_module(module_name)

        # Iterate over all members of the module
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Check if the class is a subclass of ToolInterface and is not ToolInterface itself
            if issubclass(obj, ToolInterface) and obj is not ToolInterface:
                tool_names.append(name)
                tools_and_names[name] = obj


tools_from_package(astra_assistants_tools)


def wrap_base_tool_as_tool_interface(base_tool: BaseTool) -> ToolInterface:
    """wrap_Base_tool_ass_tool_interface.

    Wrap a BaseTool instance in a new class implementing ToolInterface,
    building a dynamic Pydantic model from its args_schema (if any).
    We only call `args_schema()` if it's truly a function/method,
    avoiding accidental calls on a Pydantic model class (which is also callable).
    """
    raw_args_schema = getattr(base_tool, "args_schema", None)

    # --- 1) Distinguish between a function/method vs. class/dict/None ---
    if inspect.isfunction(raw_args_schema) or inspect.ismethod(raw_args_schema):
        # It's actually a function -> call it once to get a class or dict
        raw_args_schema = raw_args_schema()
    # Otherwise, if it's a class or dict, do nothing here

    # Now `raw_args_schema` might be:
    # - A Pydantic model class (subclass of BaseModel)
    # - A dict (JSON schema)
    # - None
    # - Something unexpected => raise error

    # --- 2) Convert the schema or model class to a JSON schema dict ---
    if raw_args_schema is None:
        # No schema => minimal
        schema_dict = {"type": "object", "properties": {}}

    elif isinstance(raw_args_schema, dict):
        # Already a JSON schema
        schema_dict = raw_args_schema

    elif inspect.isclass(raw_args_schema) and issubclass(raw_args_schema, BaseModel):
        # It's a Pydantic model class -> convert to JSON schema
        schema_dict = raw_args_schema.schema()

    else:
        msg = f"args_schema must be a Pydantic model class, a JSON schema dict, or None. Got: {raw_args_schema!r}"
        raise TypeError(msg)

    # --- 3) Build our dynamic Pydantic model from the JSON schema ---
    InputSchema: type[BaseModel] = create_input_schema_from_json_schema(schema_dict)  # noqa: N806

    # --- 4) Define a wrapper class that uses composition ---
    class WrappedDynamicTool(ToolInterface):
        """WrappedDynamicTool.

        Uses composition to delegate logic to the original base_tool,
        but sets `call(..., arguments: InputSchema)` so we have a real model.
        """

        def __init__(self, tool: BaseTool):
            self._tool = tool

        def call(self, arguments: InputSchema) -> dict:  # type: ignore # noqa: PGH003
            output = self._tool.invoke(arguments.dict())  # type: ignore # noqa: PGH003
            result = ""
            if "error" in output[0].data:
                result = output[0].data["error"]
            elif "result" in output[0].data:
                result = output[0].data["result"]
            return {"cache_id": str(uuid.uuid4()), "output": result}

        def run(self, tool_input: Any) -> str:
            return self._tool.run(tool_input)

        def name(self) -> str:
            """Return the base tool's name if it exists."""
            if hasattr(self._tool, "name"):
                return str(self._tool.name)
            return super().name()

        def to_function(self):
            """Incorporate the base tool's description if present."""
            params = InputSchema.schema()
            description = getattr(self._tool, "description", "A dynamically wrapped tool")
            return {
                "type": "function",
                "function": {"name": self.name(), "description": description, "parameters": params},
            }

    # Return an instance of our newly minted class
    return WrappedDynamicTool(base_tool)


def sync_upload(file_path, client):
    with Path(file_path).open("rb") as sync_file_handle:
        return client.files.create(
            file=sync_file_handle,  # Pass the sync file handle
            purpose="assistants",
        )
