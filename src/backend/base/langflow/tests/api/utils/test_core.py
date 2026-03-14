from langflow.api.utils.core import extract_global_variables_from_headers
from starlette.datastructures import Headers


def test_extract_global_variables_from_headers_regular_strings():
    """Test that regular strings are returned correctly as values when converted from headers to a dict."""
    headers = Headers(
        headers={
            "X-LANGFLOW-GLOBAL-VAR-API-KEY": "secret123",
            "X-LANGFLOW-GLOBAL-VAR-DATABASE-URL": "postgresql://localhost:5432/db",
            "Content-Type": "application/json",
            "Authorization": "Bearer token",
        }
    )

    result = extract_global_variables_from_headers(headers)

    assert result == {
        "API-KEY": "secret123",
        "DATABASE-URL": "postgresql://localhost:5432/db",
    }
    # Non-matching headers should not be included
    assert "CONTENT-TYPE" not in result
    assert "AUTHORIZATION" not in result


def test_extract_global_variables_from_headers_percent_encoded():
    """Test that percent-encoded strings are decoded before being returned."""
    headers = Headers(
        headers={
            "X-LANGFLOW-GLOBAL-VAR-MESSAGE": "hello%20world",
            "X-LANGFLOW-GLOBAL-VAR-PATH": "/path/with%20spaces/and%2Fslash",
            "X-LANGFLOW-GLOBAL-VAR-SPECIAL": "value%21%40%23%24%25",  # !@#$%
            "X-LANGFLOW-GLOBAL-VAR-UNICODE": "caf%C3%A9",  # café
        }
    )

    result = extract_global_variables_from_headers(headers)

    assert result == {
        "MESSAGE": "hello world",
        "PATH": "/path/with spaces/and/slash",
        "SPECIAL": "value!@#$%",
        "UNICODE": "café",
    }


def test_extract_global_variables_from_headers_mixed():
    """Test with a mix of regular and percent-encoded values."""
    headers = Headers(
        headers={
            "X-LANGFLOW-GLOBAL-VAR-REGULAR": "simple_value",
            "X-LANGFLOW-GLOBAL-VAR-ENCODED": "value%20with%20spaces",
            "X-LANGFLOW-GLOBAL-VAR-EMPTY": "",
        }
    )

    result = extract_global_variables_from_headers(headers)

    assert result == {
        "REGULAR": "simple_value",
        "ENCODED": "value with spaces",
        "EMPTY": "",
    }


def test_extract_global_variables_from_headers_case_insensitive():
    """Test that header names are case-insensitive."""
    headers = Headers(
        headers={
            "x-langflow-global-var-lowercase": "value1",
            "X-LANGFLOW-GLOBAL-VAR-UPPERCASE": "value2",
            "X-Langflow-Global-Var-MixedCase": "value3",
        }
    )

    result = extract_global_variables_from_headers(headers)

    assert result == {
        "LOWERCASE": "value1",
        "UPPERCASE": "value2",
        "MIXEDCASE": "value3",
    }


def test_extract_global_variables_from_headers_empty():
    """Test with no matching headers."""
    headers = Headers(
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer token",
        }
    )

    result = extract_global_variables_from_headers(headers)

    assert result == {}


def test_extract_global_variables_from_headers_error_handling():
    """Test that errors are handled gracefully."""
    # Test with None (should handle gracefully)
    result = extract_global_variables_from_headers(Headers())
    assert result == {}
