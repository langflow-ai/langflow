"""Data class for langflow - imports from the enhanced version.

This maintains backward compatibility while using the new inheritance approach.
"""

# Import everything from the enhanced Data class
# Import utility functions that are still needed
from lfx.schema.data import custom_serializer, serialize_data

from langflow.schema.data_enhanced import Data

__all__ = ["Data", "custom_serializer", "serialize_data"]
