# This module is used to import any langchain class by name.

import importlib
from typing import Any


def import_module(module_path: str) -> Any:
    """Import module from module path."""
    if "from" not in module_path:
        # Import the module using the module path
        return importlib.import_module(module_path)
    # Split the module path into its components
    _, module_path, _, object_name = module_path.split()

    # Import the module using the module path
    module = importlib.import_module(module_path)

    return getattr(module, object_name)


def import_class(class_path: str) -> Any:
    """Import class from class path."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = import_module(module_path)
    return getattr(module, class_name)
