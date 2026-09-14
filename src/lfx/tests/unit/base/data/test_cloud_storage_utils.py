"""Tests for base/data/cloud_storage_utils.py - Google service account key parsing."""

import json

import pytest
from lfx.base.data.cloud_storage_utils import parse_google_service_account_key

CREDENTIALS = {"type": "service_account", "project_id": "test-project"}


class TestParseGoogleServiceAccountKey:
    """Test parse_google_service_account_key input tolerance and its dict contract."""

    def test_single_encoded_json_object(self):
        assert parse_google_service_account_key(json.dumps(CREDENTIALS)) == CREDENTIALS

    def test_double_encoded_json_string(self):
        """A credential object JSON-encoded twice is decoded down to the object."""
        assert parse_google_service_account_key(json.dumps(json.dumps(CREDENTIALS))) == CREDENTIALS

    def test_double_encoded_with_surrounding_whitespace(self):
        padded = f"  \n{json.dumps(json.dumps(CREDENTIALS))}  \n"

        assert parse_google_service_account_key(padded) == CREDENTIALS

    def test_triple_encoded_json_string(self):
        """Three layers are within the decode bound, so they still resolve."""
        assert parse_google_service_account_key(json.dumps(json.dumps(json.dumps(CREDENTIALS)))) == CREDENTIALS

    def test_single_encoded_with_surrounding_whitespace(self):
        assert parse_google_service_account_key(f"  \n{json.dumps(CREDENTIALS)}  \n") == CREDENTIALS

    def test_non_breaking_space_padding(self):
        """The up-front strip() exists for this: json.loads rejects U+00A0 padding."""
        padded = f"\xa0{json.dumps(CREDENTIALS)}\xa0"

        assert parse_google_service_account_key(padded) == CREDENTIALS

    def test_literal_control_characters_in_private_key(self):
        """Raw newlines inside a pasted private_key must not fail the parse."""
        key = '{"type": "service_account", "private_key": "-----BEGIN KEY-----\nFAKE\n-----END KEY-----"}'

        result = parse_google_service_account_key(key)

        assert result["type"] == "service_account"
        assert "BEGIN KEY" in result["private_key"]

    def test_escaped_newlines_in_private_key(self):
        """Escaped newlines are ordinary JSON escapes and need no special handling."""
        key = '{"type": "service_account", "private_key": "-----BEGIN KEY-----\\nFAKE\\n-----END KEY-----"}'

        result = parse_google_service_account_key(key)

        assert result["type"] == "service_account"
        assert "\n" in result["private_key"]

    @pytest.mark.parametrize(
        ("raw", "type_name"),
        [("42", "int"), ("[1, 2]", "list"), ("null", "NoneType"), ('"plain text"', "str")],
    )
    def test_rejects_json_that_is_not_an_object(self, raw, type_name):
        """Valid JSON that is not an object is rejected, and the error names the type."""
        with pytest.raises(ValueError, match=f"expected a JSON object, got {type_name}") as exc_info:
            parse_google_service_account_key(raw)

        # Regression guard: these inputs used to return the non-dict value, or raise
        # with an empty detail list.
        assert str(exc_info.value).count("expected a JSON object") == 1

    def test_rejects_non_json_garbage(self):
        with pytest.raises(ValueError, match="Unable to parse service account key JSON"):
            parse_google_service_account_key("not json at all")

    def test_rejects_empty_input(self):
        with pytest.raises(ValueError, match="Unable to parse service account key JSON"):
            parse_google_service_account_key("")

    def test_truncated_inner_payload_reports_the_inner_error(self):
        """A double-encoded key whose inner JSON is cut short keeps the syntax position."""
        truncated = json.dumps('{"type": "service_account", "project_id"')

        with pytest.raises(ValueError, match="inner layer") as exc_info:
            parse_google_service_account_key(truncated)

        message = str(exc_info.value)
        assert "expected a JSON object, got str" in message
        assert "line 1 column" in message
        # The inner error carries only a position, never the document itself.
        assert "service_account" not in message
