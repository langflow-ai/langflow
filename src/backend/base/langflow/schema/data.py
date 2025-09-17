"""Data class for langflow - imports from lfx.

This maintains backward compatibility while using the lfx implementation.
"""

from lfx.schema.data import Data, custom_serializer, serialize_data

__all__ = ["Data", "custom_serializer", "serialize_data"]
