import json

import pytest
from lfx.base.data.cloud_storage_utils import parse_google_service_account_key


def test_parse_google_service_account_key_accepts_json_object():
    """A normal JSON object is returned unchanged."""
    credentials = {"type": "service_account", "project_id": "test-project"}

    assert parse_google_service_account_key(json.dumps(credentials)) == credentials


def test_parse_google_service_account_key_decodes_double_encoded_json():
    """A JSON string containing a credential object is decoded twice."""
    credentials = {"type": "service_account", "project_id": "test-project"}
    double_encoded_credentials = json.dumps(json.dumps(credentials))

    assert parse_google_service_account_key(double_encoded_credentials) == credentials


@pytest.mark.parametrize("credentials", ["[]", "null", "42"])
def test_parse_google_service_account_key_rejects_non_object_json(credentials):
    """Valid JSON values that are not objects are rejected."""
    with pytest.raises(ValueError, match=r"Unable to parse|Parsed value must be an object"):
        parse_google_service_account_key(credentials)


def test_parse_google_service_account_key_rejects_invalid_inner_json():
    """A JSON string containing invalid JSON reports the nested parse failure."""
    invalid_inner_json = json.dumps("not valid JSON")

    with pytest.raises(ValueError, match="Double-encoded parse"):
        parse_google_service_account_key(invalid_inner_json)
