# Forward import for converter utilities
# We intentionally keep this file, as the redirect to lfx in components/__init__.py
# only supports direct imports from lfx.components, not sub-modules.
#
# This allows imports from langflow.components.processing.converter. to still function.
from lfx.components.processing.converter import convert_to_dataframe

__all__ = ["convert_to_dataframe"]
