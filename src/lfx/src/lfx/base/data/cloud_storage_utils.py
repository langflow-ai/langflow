"""Shared utilities for cloud storage operations (AWS S3 and Google Drive).

This module provides common functionality used by both read and write file components
to avoid code duplication.
"""

from __future__ import annotations

import json
import os
from typing import Any

from lfx.utils.secrets import secret_value_to_str


def _resolve_aws_credentials(component: Any) -> tuple[str | None, str | None, bool, bool]:
    aws_access_key_id = secret_value_to_str(getattr(component, "aws_access_key_id", None))
    access_key_from_environment = not aws_access_key_id
    if access_key_from_environment:
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")

    aws_secret_access_key = secret_value_to_str(getattr(component, "aws_secret_access_key", None))
    secret_key_from_environment = not aws_secret_access_key
    if secret_key_from_environment:
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    return aws_access_key_id, aws_secret_access_key, access_key_from_environment, secret_key_from_environment


def get_s3_bucket_name(component: Any) -> str | None:
    """Resolve the S3 bucket from the component input or storage settings."""
    bucket_name = getattr(component, "bucket_name", None)
    if bucket_name:
        return str(bucket_name)

    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    configured_bucket = getattr(settings_service.settings, "object_storage_bucket_name", None)
    return str(configured_bucket) if configured_bucket else None


def validate_aws_credentials(component: Any) -> None:
    """Validate that required AWS S3 credentials are present.

    Args:
        component: Component instance with AWS credential attributes

    Raises:
        ValueError: If any required credential is missing
    """
    aws_access_key_id, aws_secret_access_key, _, _ = _resolve_aws_credentials(component)
    if not aws_access_key_id:
        msg = (
            "AWS Access Key ID is required for S3 storage. Provide it as a component input "
            "or set AWS_ACCESS_KEY_ID environment variable."
        )
        raise ValueError(msg)
    if not aws_secret_access_key:
        msg = (
            "AWS Secret Key is required for S3 storage. Provide it as a component input "
            "or set AWS_SECRET_ACCESS_KEY environment variable."
        )
        raise ValueError(msg)
    if not get_s3_bucket_name(component):
        msg = (
            "S3 Bucket Name is required for S3 storage. Provide it as a component input "
            "or set LANGFLOW_OBJECT_STORAGE_BUCKET_NAME environment variable."
        )
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

    aws_access_key_id, aws_secret_access_key, access_key_from_environment, secret_key_from_environment = (
        _resolve_aws_credentials(component)
    )
    client_config: dict[str, str] = {
        "aws_access_key_id": str(aws_access_key_id),
        "aws_secret_access_key": str(aws_secret_access_key),
    }

    if access_key_from_environment and secret_key_from_environment:
        aws_session_token = os.getenv("AWS_SESSION_TOKEN")
        if aws_session_token:
            client_config["aws_session_token"] = aws_session_token

    aws_region = getattr(component, "aws_region", None) or os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
    if aws_region:
        client_config["region_name"] = str(aws_region)

    return boto3.client("s3", **client_config)


def parse_google_service_account_key(service_account_key: Any) -> dict:
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
    service_account_key = secret_value_to_str(service_account_key) or ""

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
