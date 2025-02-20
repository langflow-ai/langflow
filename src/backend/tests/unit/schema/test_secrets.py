import pytest
from langflow.schema.secrets import DataRedactionModel


class TestRedactionModel(DataRedactionModel):
    name: str
    message: str
    type: str


def test_log_serialization_no_secrets():
    """Test log serialization with no secrets in the message."""
    log = TestRedactionModel(name="test_log", message="This is a test message without secrets.", type="test")
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert serialized_log["message"] == "This is a test message without secrets."


@pytest.mark.parametrize(
    "secret_message",
    [
        "api_key=1234567890abcdef1234567890abcdef",
        "AWS_SECRET_KEY=AKIAIOSFODNN7EXAMPLE1234",
        "password=super_secret_password123",
        "bearer_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    ],
)
def test_log_serialization_known_secrets(secret_message):
    """Test log serialization with known secret patterns are properly masked."""
    log = TestRedactionModel(name="secret_log", message=secret_message, type="test")
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert serialized_log["message"] == "[Secret Redacted]"


def test_log_serialization_mixed_content():
    """Test log serialization with mixed content (secrets and non-secrets)."""
    mixed_message = "Hello world! My API key is 1234567890abcdef1234567890abcdef"
    log = TestRedactionModel(name="mixed_log", message=mixed_message, type="test")
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert serialized_log["message"] == "[Secret Redacted]"


def test_log_serialization_multiple_secrets():
    """Test log serialization with multiple secrets in the message."""
    multiple_secrets_message = """
    First secret: api_key=1234567890abcdef1234567890abcdef
    Second secret: password=secret123
    """
    log = TestRedactionModel(name="multiple_secrets_log", message=multiple_secrets_message, type="test")
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert serialized_log["message"] == "[Secret Redacted]"


def test_log_serialization_special_characters():
    """Test log serialization with special characters in the message."""
    special_chars_message = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    log = TestRedactionModel(name="special_chars_log", message=special_chars_message, type="test")
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert serialized_log["message"] == special_chars_message


def test_log_serialization_empty_string():
    """Test log serialization with an empty string message."""
    log = TestRedactionModel(name="empty_log", message="", type="test")
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert serialized_log["message"] == ""


def test_log_serialization_unicode_message():
    """Test log serialization with a unicode message."""
    unicode_message = "你好世界"
    log = TestRedactionModel(name="unicode_log", message=unicode_message, type="test")
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert serialized_log["message"] == unicode_message


def test_log_serialization_non_string_message():
    """Test log serialization with a non-string message (e.g., a number)."""
    non_string_message = 12345
    log = TestRedactionModel(name="non_string_log", message=str(non_string_message), type="test")
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert serialized_log["message"] == "12345"


def test_log_serialization_pydantic_error_message():
    """Test log serialization when message causes a PydanticSerializationError."""

    class ErrorObject:
        def __repr__(self):
            msg = "Simulated PydanticSerializationError"
            raise ValueError(msg)

    error_message = ErrorObject()
    log = TestRedactionModel(name="error_log", message=str(error_message), type="test")
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert "Error" in serialized_log["message"]


def test_log_serialization_unicode_decode_error_message():
    """Test log serialization when message causes a UnicodeDecodeError."""
    byte_message = b"\x80abc"  # Invalid UTF-8 byte
    log = TestRedactionModel(
        name="unicode_decode_error_log", message=byte_message.decode("latin-1"), type="test"
    )  # decode with latin-1 to avoid immediate error
    serialized_log = log.serialize_log_without_secrets(lambda x: x.model_dump())
    assert "\\x80abc" in serialized_log["message"]
