from uuid import UUID


def has_user_id(user_id: UUID | str | None) -> bool:
    """Return whether a user ID is neither None nor the serialized string 'None'."""
    return user_id is not None and str(user_id) != "None"
