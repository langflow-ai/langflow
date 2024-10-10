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

import langflow.components.astra_assistants.tools as langflow_assistant_tools

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
litellm_model_names = []
for model, _ in data.items():
    if model != "sample_spec":
        # litellm_model_names.append(f"{details['litellm_provider']}/{model}")
        litellm_model_names.append(model)


# To store the class names that extend ToolInterface
tool_names = []
tools_and_names = {}


def tools_from_package(pkg):
    # Helper function to process a module or package
    def process_module_or_package(package_name, package_path):
        for module_info in pkgutil.iter_modules(package_path):
            module_name = f"{package_name}.{module_info.name}"

            # Dynamically import the module
            module = importlib.import_module(module_name)

            # If the module is a package itself, recurse into it
            if module_info.ispkg:
                process_module_or_package(module_name, module.__path__)
            else:
                # Iterate over all members of the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if the class is a subclass of ToolInterface and is not ToolInterface itself
                    if issubclass(obj, ToolInterface) and obj is not ToolInterface:
                        tool_names.append(name)
                        tools_and_names[name] = obj

    # Start processing from the top-level package
    package_name = pkg.__name__
    process_module_or_package(package_name, pkg.__path__)


tools_from_package(astra_assistants_tools)
tools_from_package(langflow_assistant_tools)
