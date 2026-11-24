"""Unit tests for the KB user-metadata validator.

Locks down the contract enforced by ``parse_user_metadata`` /
``parse_per_file_metadata`` so the API boundary cannot drift from the
client-side validation rules without these tests breaking first.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from langflow.api.utils.kb_metadata import (
    parse_per_file_metadata,
    parse_user_metadata,
    validate_user_metadata,
)


class TestParseUserMetadata:
    def test_empty_returns_dict(self):
        assert parse_user_metadata(None) == {}
        assert parse_user_metadata("") == {}

    def test_valid_payload_round_trips(self):
        result = parse_user_metadata('{"category": "invoice", "year": 2026}')
        assert result == {"category": "invoice", "year": 2026}

    def test_array_value_accepted(self):
        result = parse_user_metadata('{"tag": ["urgent", "audit"]}')
        assert result == {"tag": ["urgent", "audit"]}

    def test_invalid_json_rejected(self):
        with pytest.raises(HTTPException) as excinfo:
            parse_user_metadata("{not-json")
        assert excinfo.value.status_code == 422
        assert "valid JSON" in excinfo.value.detail

    def test_non_dict_rejected(self):
        with pytest.raises(HTTPException) as excinfo:
            parse_user_metadata("[1, 2, 3]")
        assert excinfo.value.status_code == 422
        assert "JSON object" in excinfo.value.detail

    @pytest.mark.parametrize(
        "key",
        [
            "Source",  # uppercase
            "tag-name",  # hyphen disallowed
            "tag.name",  # dot disallowed
            "",  # empty
            "x" * 33,  # exceeds 32-char cap
        ],
    )
    def test_invalid_keys_rejected(self, key):
        with pytest.raises(HTTPException) as excinfo:
            validate_user_metadata({key: "x"})
        assert excinfo.value.status_code == 422

    @pytest.mark.parametrize(
        "key",
        [
            "source",
            "file_name",
            "chunk_index",
            "total_chunks",
            "ingested_at",
            "job_id",
            "source_type",
            "source_metadata",
        ],
    )
    def test_reserved_keys_rejected(self, key):
        with pytest.raises(HTTPException) as excinfo:
            validate_user_metadata({key: "x"})
        assert excinfo.value.status_code == 422
        assert "reserved" in excinfo.value.detail

    def test_too_many_keys_rejected(self):
        payload = {f"k{i}": "x" for i in range(17)}
        with pytest.raises(HTTPException) as excinfo:
            validate_user_metadata(payload)
        assert excinfo.value.status_code == 422
        assert "key limit" in excinfo.value.detail

    def test_string_value_too_long_rejected(self):
        with pytest.raises(HTTPException) as excinfo:
            validate_user_metadata({"k": "x" * 257})
        assert excinfo.value.status_code == 422

    def test_array_too_long_rejected(self):
        with pytest.raises(HTTPException) as excinfo:
            validate_user_metadata({"tag": ["x"] * 17})
        assert excinfo.value.status_code == 422

    def test_array_non_string_entry_rejected(self):
        with pytest.raises(HTTPException) as excinfo:
            validate_user_metadata({"tag": ["a", 1, "b"]})
        assert excinfo.value.status_code == 422

    def test_nested_object_rejected(self):
        with pytest.raises(HTTPException) as excinfo:
            validate_user_metadata({"k": {"nested": "value"}})
        assert excinfo.value.status_code == 422

    def test_numeric_and_bool_accepted(self):
        result = validate_user_metadata({"count": 5, "active": True, "ratio": 0.5})
        assert result == {"count": 5, "active": True, "ratio": 0.5}


class TestParsePerFileMetadata:
    def test_empty_returns_dict(self):
        assert parse_per_file_metadata(None) == {}
        assert parse_per_file_metadata("") == {}

    def test_valid_payload(self):
        result = parse_per_file_metadata('{"a.pdf": {"tag": "x"}, "b.pdf": {"tag": "y"}}')
        assert result == {"a.pdf": {"tag": "x"}, "b.pdf": {"tag": "y"}}

    def test_non_dict_rejected(self):
        with pytest.raises(HTTPException) as excinfo:
            parse_per_file_metadata('["a.pdf"]')
        assert excinfo.value.status_code == 422

    def test_per_file_inner_validates(self):
        with pytest.raises(HTTPException) as excinfo:
            parse_per_file_metadata('{"a.pdf": {"source": "x"}}')
        # Reserved key reuses the run-level validator.
        assert excinfo.value.status_code == 422
        assert "reserved" in excinfo.value.detail

    def test_too_many_files_rejected(self):
        payload_dict = {f"f{i}.pdf": {"k": "v"} for i in range(17)}
        import json

        with pytest.raises(HTTPException) as excinfo:
            parse_per_file_metadata(json.dumps(payload_dict))
        assert excinfo.value.status_code == 422
