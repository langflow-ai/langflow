
from uuid import UUID

MISSING_USER_OR_ITEM_ID_MSG = "user_id and {item_type}_id are required."
MISSING_USER_ID_MSG = "user_id is required."


def get_uuid(value: str | UUID) -> UUID:
    """Get a UUID from a string or UUID."""
    return UUID(value) if isinstance(value, str) else value


def require_user_and_item_ids(
    user_id: str | UUID | None,
    flow_id: str | UUID | None,
    item_type: str
    ):
    """Raise a ValueError if user_id or flow_id is not provided."""
    if not (user_id and flow_id):
        raise ValueError(MISSING_USER_OR_ITEM_ID_MSG.format(item_type=item_type))


def require_user_id(
    user_id: str | UUID | None,
    ):
    """Raise a ValueError if user_id or flow_id is not provided."""
    if not user_id:
        raise ValueError(MISSING_USER_ID_MSG)
