"""JSON and Data classes for langflow - imports from lfx.

This maintains backward compatibility while using the lfx implementation.
JSON is the new base type; Data is an alias for backwards compatibility.
"""

from lfx.schema.data import JSON, Data, custom_serializer, serialize_data

__all__ = ["JSON", "Data", "custom_serializer", "serialize_data"]
