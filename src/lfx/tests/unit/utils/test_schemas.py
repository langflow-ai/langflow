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
    with pytest.raises(ValidationError, match="Input should be a valid string"):
        ChatOutputResponse(message="hello", session_id=123, type="text")
