import pytest
from detect_secrets.core.potential_secret import PotentialSecret
from hypothesis import given
from hypothesis import strategies as st
from langflow.schema.secrets import check_string_for_secrets

# Strategy for regular readable text without secrets
readable_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll",),  # Only lowercase letters
        blacklist_characters="=",  # Exclude equals sign as it's often used in secrets
    ),
    min_size=1,
    max_size=10,  # Limit size to avoid generating long strings that might look like secrets
)

# Strategy for potential API keys and secrets
api_key_pattern = st.from_regex(
    r"[A-Za-z0-9]{32,}",  # Common pattern for API keys
    fullmatch=True,
)


@given(st.text(min_size=1))
def test_consistent_return_type(text):
    """Test that the function always returns a tuple of (list, str) and processes any input string."""
    result, masked = check_string_for_secrets(text)
    assert isinstance(result, list)
    assert isinstance(masked, str)
    # Each detected secret should be a PotentialSecret instance
    for secret in result:
        assert isinstance(secret, PotentialSecret)


@pytest.mark.parametrize(
    "secret_text",
    [
        "api_key=1234567890abcdef1234567890abcdef",
        "AWS_SECRET_KEY=AKIAIOSFODNN7EXAMPLE1234",
        "password=super_secret_password123",
        "bearer_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    ],
)
def test_known_secrets_are_detected_and_masked(secret_text):
    """Test that known secret patterns are properly detected and masked."""
    result, masked = check_string_for_secrets(secret_text)
    assert isinstance(result, list)
    # Known secrets should be detected
    assert len(result) > 0
    # The result should contain information about the detected secret
    first_detection = result[0]
    assert isinstance(first_detection, PotentialSecret)
    assert hasattr(first_detection, "type")
    assert hasattr(first_detection, "line_number")
    # Verify masking
    assert masked == "[Secret Redacted]"


@given(api_key_pattern)
def test_generated_api_keys(api_key):
    """Test that generated API key patterns are detected as secrets and properly masked."""
    test_string = f"api_key={api_key}"
    result, masked = check_string_for_secrets(test_string)
    assert isinstance(result, list)
    # API keys should be detected as secrets
    assert len(result) > 0
    assert isinstance(result[0], PotentialSecret)
    # Verify masking format
    assert masked == "[Secret Redacted]"


def test_empty_string():
    """Test that empty string is handled properly."""
    result, masked = check_string_for_secrets("")
    assert isinstance(result, list)
    assert len(result) == 0
    assert masked == ""


@pytest.mark.parametrize(
    "mixed_text",
    [
        "Hello world! My API key is 1234567890abcdef1234567890abcdef",
        "Regular text\npassword=secret123\nMore regular text",
    ],
)
def test_mixed_content(mixed_text):
    """Test strings containing both regular text and secrets."""
    result, masked = check_string_for_secrets(mixed_text)
    assert isinstance(result, list)
    # Should detect the secret part
    assert len(result) > 0
    assert isinstance(result[0], PotentialSecret)
    # Verify masking
    assert masked == "[Secret Redacted]"


def test_multiline_string():
    """Test that multiline strings are processed correctly."""
    multiline = """
    First line
    password=secret123
    Third line
    """
    result, masked = check_string_for_secrets(multiline)
    assert isinstance(result, list)
    for secret in result:
        assert isinstance(secret, PotentialSecret)
    # Verify that the password is masked but other lines are intact
    assert masked == "[Secret Redacted]"


def test_special_characters():
    """Test that strings with special characters are handled properly."""
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    result, masked = check_string_for_secrets(special_chars)
    assert isinstance(result, list)
    for secret in result:
        assert isinstance(secret, PotentialSecret)
    # Special characters string should remain unchanged if no secrets detected
    if not result:
        assert masked == special_chars


def test_short_secrets():
    """Test that short secrets (4 characters or less) are fully masked."""
    short_secret = "key=1234"  # noqa: S105
    result, masked = check_string_for_secrets(short_secret)
    assert isinstance(result, list)
    if result:  # If detected as a secret
        assert masked == "[Secret Redacted]"


def test_multiple_secrets():
    """Test that multiple secrets in the same string are all properly masked."""
    text_with_multiple_secrets = """
    First secret: api_key=1234567890abcdef1234567890abcdef
    Second secret: password=secret123
    Third secret: AWS_KEY=AKIAIOSFODNN7EXAMPLE1234
    """
    result, masked = check_string_for_secrets(text_with_multiple_secrets)
    assert isinstance(result, list)
    assert len(result) > 1  # Should detect multiple secrets

    # Verify all secrets are masked
    assert masked == "[Secret Redacted]"
