"""Data class for langflow - imports from lfx.

This maintains backward compatibility while using the lfx implementation.
"""

from lfx.schema.data import JSON, Data, custom_serializer, serialize_data

__all__ = ["JSON", "Data", "custom_serializer", "serialize_data"]
