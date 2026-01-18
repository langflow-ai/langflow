
from uuid import UUID

from langflow.services.database.models.flow_history.schema import IDType

MISSING_USER_OR_ITEM_ID_MSG = "user_id and {item_type}_id are required."
MISSING_USER_ID_MSG = "user_id is required."

########################################################
# validation
########################################################
MISSING_ALL_ID_MSG = "user_id and {item_type}_id are required."

class MissingIdError(ValueError):
    """Raised when a required id is missing."""

def require_all_ids(
    user_id: IDType,
    item_id: IDType,
    item_type: str
    ):
    """Raises a ValueError if the user or item id is None or empty."""
    if not (user_id and item_id):
        raise MissingIdError(MISSING_ALL_ID_MSG.format(item_type=item_type))

def get_uuid(value: str | UUID) -> UUID:
    """Get a UUID from a string or UUID."""
    return UUID(value) if isinstance(value, str) else value


