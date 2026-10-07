from typing import overload
from uuid import UUID


def has_user_id(user_id: UUID | str | None) -> bool:
    """Return whether a user ID is neither None nor the serialized string 'None'."""
    return user_id is not None and str(user_id) != "None"


@overload
def to_user_uuid(user_id: UUID | str) -> UUID: ...


@overload
def to_user_uuid(user_id: None) -> None: ...


def to_user_uuid(user_id: UUID | str | None) -> UUID | None:
    """Convert string user IDs to UUIDs, preserving UUID objects and None."""
    return UUID(user_id) if isinstance(user_id, str) else user_id
