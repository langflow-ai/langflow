from uuid import uuid4

import pytest
from lfx.utils.schemas import ChatOutputResponse
from pydantic import ValidationError


def test_chat_output_response_coerces_uuid_session_id():
    """Model-level coercion should convert UUID session_id to string."""
    session_id = uuid4()
    response = ChatOutputResponse(message="hello", session_id=session_id, type="text")
    assert response.session_id == str(session_id)


def test_chat_output_response_rejects_non_string_non_uuid_session_id():
    """Non-string/non-UUID session_id should still fail validation."""
    with pytest.raises(ValidationError, match="must be a UUID, string, or None"):
        ChatOutputResponse(message="hello", session_id=123, type="text")


def test_chat_output_response_accepts_none_session_id():
    """None session_id should be accepted as-is."""
    response = ChatOutputResponse(message="hello", session_id=None, type="text")
    assert response.session_id is None


def test_chat_output_response_accepts_string_session_id():
    """String session_id should be accepted unchanged."""
    response = ChatOutputResponse(message="hello", session_id="session-123", type="text")
    assert response.session_id == "session-123"


@pytest.mark.parametrize("invalid_session_id", [{}, [], object()])
def test_chat_output_response_rejects_other_invalid_session_id_types(invalid_session_id):
    """Other non-string/non-UUID session_id types should fail validation."""
    with pytest.raises(ValidationError, match="must be a UUID, string, or None"):
        ChatOutputResponse(message="hello", session_id=invalid_session_id, type="text")
