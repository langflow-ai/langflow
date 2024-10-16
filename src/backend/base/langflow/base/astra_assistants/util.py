import importlib
import inspect
import json
import os
import pkgutil
import threading

import astra_assistants.tools as astra_assistants_tools
import requests
from astra_assistants import OpenAI, patch
from astra_assistants.tools.tool_interface import ToolInterface

client_lock = threading.Lock()
client = None


def get_patched_openai_client(shared_component_cache):
    os.environ["ASTRA_ASSISTANTS_QUIET"] = "true"
    client = shared_component_cache.get("client")
    if client is None:
        client = patch(OpenAI())
        shared_component_cache.set("client", client)
    return client


url = "https://raw.githubusercontent.com/BerriAI/litellm/refs/heads/main/model_prices_and_context_window.json"
response = requests.get(url)
data = json.loads(response.text)

# Extract the model names into a Python list
litellm_model_names = [model for model in data if model != "sample_spec"]


# To store the class names that extend ToolInterface
tool_names = []
tools_and_names = {}


def tools_from_package(your_package):
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
