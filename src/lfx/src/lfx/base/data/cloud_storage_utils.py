"""Shared utilities for cloud storage operations (AWS S3 and Google Drive).

This module provides common functionality used by both read and write file components
to avoid code duplication.
"""

from __future__ import annotations

import json
from typing import Any


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


def parse_google_service_account_key(service_account_key: str) -> dict:
    """Parse Google service account JSON key with multiple fallback strategies.

    This function handles various common formatting issues when users paste
    service account keys, including:
    - Control characters
    - Extra whitespace
    - Double-encoded JSON strings
    - Escaped newlines in private_key field

    Args:
        service_account_key: Service account JSON key as string

    Returns:
        dict: Parsed service account credentials

    Raises:
        ValueError: If all parsing strategies fail
    """
    credentials_dict = None
    parse_errors = []

    # Strategy 1: Parse as-is with strict=False to allow control characters
    try:
        credentials_dict = json.loads(service_account_key, strict=False)
    except json.JSONDecodeError as e:
        parse_errors.append(f"Standard parse: {e!s}")

    # Strategy 2: Strip whitespace and try again
    if credentials_dict is None:
        try:
            cleaned_key = service_account_key.strip()
            credentials_dict = json.loads(cleaned_key, strict=False)
        except json.JSONDecodeError as e:
            parse_errors.append(f"Stripped parse: {e!s}")

    # Strategy 3: Check if it's double-encoded (JSON string of a JSON string)
    if credentials_dict is None:
        try:
            decoded_once = json.loads(service_account_key, strict=False)
            credentials_dict = json.loads(decoded_once, strict=False) if isinstance(decoded_once, str) else decoded_once
        except json.JSONDecodeError as e:
            parse_errors.append(f"Double-encoded parse: {e!s}")

    # Strategy 4: Try to fix common issues with newlines in the private_key field
    if credentials_dict is None:
        try:
            # Replace literal \n with actual newlines which is common in pasted JSON
            fixed_key = service_account_key.replace("\\n", "\n")
            credentials_dict = json.loads(fixed_key, strict=False)
        except json.JSONDecodeError as e:
            parse_errors.append(f"Newline-fixed parse: {e!s}")

    if credentials_dict is None:
        error_details = "; ".join(parse_errors)
        msg = (
            f"Unable to parse service account key JSON. Tried multiple strategies: {error_details}. "
            "Please ensure you've copied the entire JSON content from your service account key file. "
            "The JSON should start with '{' and contain fields like 'type', 'project_id', 'private_key', etc."
        )
        raise ValueError(msg)

    return credentials_dict


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
