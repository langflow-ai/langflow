"""Shared utilities for cloud storage operations (AWS S3 and Google Drive).

This module provides common functionality used by both read and write file components
to avoid code duplication.
"""

from __future__ import annotations

import json
from typing import Any

from lfx.utils.secrets import secret_value_to_str


def validate_aws_credentials(component: Any) -> None:
    """Validate that required AWS S3 credentials are present.

    Args:
        component: Component instance with AWS credential attributes

    Raises:
        ValueError: If any required credential is missing
    """
    if not getattr(component, "aws_access_key_id", None):
        msg = "AWS Access Key ID is required for S3 storage"
        raise ValueError(msg)
    if not getattr(component, "aws_secret_access_key", None):
        msg = "AWS Secret Key is required for S3 storage"
        raise ValueError(msg)
    if not getattr(component, "bucket_name", None):
        msg = "S3 Bucket Name is required for S3 storage"
        raise ValueError(msg)


def create_s3_client(component: Any):
    """Create and return a configured boto3 S3 client.

    Args:
        component: Component instance with AWS credential attributes

    Returns:
        boto3 S3 client instance

    Raises:
        ImportError: If boto3 is not installed
    """
    try:
        import boto3
    except ImportError as e:
        msg = "boto3 is not installed. Please install it using `uv pip install boto3`."
        raise ImportError(msg) from e

    client_config = {
        "aws_access_key_id": component.aws_access_key_id,
        "aws_secret_access_key": component.aws_secret_access_key,
    }

    if hasattr(component, "aws_region") and component.aws_region:
        client_config["region_name"] = component.aws_region

    return boto3.client("s3", **client_config)


# Successful json.loads passes, including the first. The extra passes run only while the
# result is still a string, which is what unwraps a double-encoded key.
_MAX_JSON_DECODE_PASSES = 3


def _parse_error_message(detail: str) -> str:
    """Build the user-facing ValueError message for a key that could not be parsed."""
    return (
        f"Unable to parse service account key JSON: {detail}. "
        "Please ensure you've copied the entire JSON content from your service account key file. "
        "The JSON should start with '{' and contain fields like 'type', 'project_id', 'private_key', etc."
    )


def parse_google_service_account_key(service_account_key: Any) -> dict:
    """Parse a Google service account JSON key, tolerating common paste damage.

    Handles control characters, surrounding whitespace, and keys that have been
    JSON-encoded more than once.

    Args:
        service_account_key: Service account JSON key as string

    Returns:
        dict: Parsed service account credentials

    Raises:
        ValueError: If the key is not valid JSON, or does not decode to a JSON object
    """
    # json.loads already skips JSON whitespace, but a pasted key can carry padding the
    # scanner rejects, such as a non-breaking space. strict=False allows the control
    # characters that survive a copied private_key.
    key_text = (secret_value_to_str(service_account_key) or "").strip()

    try:
        decoded: Any = json.loads(key_text, strict=False)
    except json.JSONDecodeError:
        # Some single-line secrets escape formatting newlines outside JSON strings.
        # Preserve that repair fallback, but leave successfully parsed JSON untouched.
        try:
            decoded = json.loads(key_text.replace("\\n", "\n"), strict=False)
        except json.JSONDecodeError as e:
            msg = _parse_error_message(str(e))
            raise ValueError(msg) from e

    # Secret and configuration pipelines sometimes JSON-encode the credential object a
    # second time, so a successful decode can still yield the object as text.
    inner_error: json.JSONDecodeError | None = None
    for _ in range(_MAX_JSON_DECODE_PASSES - 1):
        if not isinstance(decoded, str):
            break
        try:
            decoded = json.loads(decoded, strict=False)
        except json.JSONDecodeError as e:
            # The inner text is not JSON, so this is the final value. Keep the error:
            # it carries the position of the real syntax problem.
            inner_error = e
            break

    if isinstance(decoded, dict):
        return decoded

    detail = f"expected a JSON object, got {type(decoded).__name__}"
    if inner_error is not None:
        detail = f"{detail}; inner layer: {inner_error!s}"
    msg = _parse_error_message(detail)
    raise ValueError(msg)


def create_google_drive_service(service_account_key: str, scopes: list[str], *, return_credentials: bool = False):
    """Create and return a configured Google Drive API service.

    Args:
        service_account_key: Service account JSON key as string
        scopes: List of Google API scopes to request
        return_credentials: If True, return both service and credentials as tuple

    Returns:
        Google Drive API service instance, or tuple of (service, credentials) if return_credentials=True

    Raises:
        ImportError: If Google API client libraries are not installed
        ValueError: If credentials cannot be parsed
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as e:
        msg = "Google API client libraries are not installed. Please install them."
        raise ImportError(msg) from e

    credentials_dict = parse_google_service_account_key(service_account_key)

    credentials = service_account.Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    service = build("drive", "v3", credentials=credentials)

    if return_credentials:
        return service, credentials
    return service
