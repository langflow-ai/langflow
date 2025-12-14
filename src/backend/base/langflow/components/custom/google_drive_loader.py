import base64
import json
import tempfile
import time
from pathlib import Path

import requests
from loguru import logger

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, Output, SecretStrInput
from langflow.schema import Data
from langflow.schema.message import Message

# Constants
REQUEST_TIMEOUT = 30  # seconds
HTTP_NOT_FOUND = 404


class GoogleDriveLoader(Component):
    """Load files from Google Drive using Service Account."""

    display_name = "Google Drive Loader"
    description = "Load files from Google Drive using Service Account"

    inputs = [
        SecretStrInput(
            name="service_account_json",
            display_name="Service Account JSON",
            info="Service Account JSON key content",
            required=True,
        ),
        MessageTextInput(
            name="file_id",
            display_name="File ID",
            info="Google Drive File ID (from URL)",
            required=True,
        ),
        DropdownInput(
            name="output_type",
            display_name="Output Type",
            info="Choose output format for images",
            options=["Message (for LLM)", "Base64 Data URL", "Raw Data"],
            value="Message (for LLM)",
        ),
    ]

    outputs = [
        Output(display_name="Content", name="content", method="load_file"),
    ]

    def get_access_token(self, service_account_info: dict) -> str:
        """Get access token from Service Account."""
        import jwt

        now = int(time.time())
        payload = {
            "iss": service_account_info["client_email"],
            "scope": "https://www.googleapis.com/auth/drive.readonly",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }

        signed_jwt = jwt.encode(
            payload,
            service_account_info["private_key"],
            algorithm="RS256",
        )

        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": signed_jwt,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def load_file(self) -> Data | Message:
        """Load a file from Google Drive."""
        # Validate inputs
        if not self.service_account_json or not self.service_account_json.strip():
            msg = "Service Account JSON is empty. Please provide the JSON key content."
            raise ValueError(msg)

        if not self.file_id or not self.file_id.strip():
            msg = "File ID is empty. Please provide a Google Drive file ID."
            raise ValueError(msg)

        # Parse Service Account JSON (strict=False to allow control characters)
        try:
            service_account_info = json.loads(self.service_account_json, strict=False)
        except json.JSONDecodeError as e:
            msg = f"Invalid Service Account JSON: {e}. Make sure you paste the complete JSON content."
            raise ValueError(msg) from e

        client_email = service_account_info.get("client_email", "unknown")
        logger.info(f"Using Service Account: {client_email}")
        logger.info(f"Loading file ID: {self.file_id}")

        # Get access token
        access_token = self.get_access_token(service_account_info)
        logger.debug("Access token obtained successfully")

        headers = {"Authorization": f"Bearer {access_token}"}

        # Get file metadata
        meta_url = f"https://www.googleapis.com/drive/v3/files/{self.file_id}"
        meta_response = requests.get(
            meta_url,
            headers=headers,
            params={
                "fields": "name,mimeType",
                "supportsAllDrives": "true",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if not meta_response.ok:
            error_detail = meta_response.text
            logger.error(f"Google Drive API error: {meta_response.status_code} - {error_detail}")
            if meta_response.status_code == HTTP_NOT_FOUND:
                msg = (
                    f"File not found (ID: {self.file_id}). "
                    "Please check: 1) File ID is correct, "
                    "2) File is shared with the Service Account email, "
                    "3) Service Account has at least 'Viewer' permission. "
                    f"API Response: {error_detail}"
                )
                raise ValueError(msg)
            msg = f"Google Drive API error: {meta_response.status_code} - {error_detail}"
            raise ValueError(msg)
        metadata = meta_response.json()

        mime_type = metadata.get("mimeType", "")
        file_name = metadata.get("name", "")

        # Google Docs formats need export
        export_formats = {
            "application/vnd.google-apps.document": "text/plain",
            "application/vnd.google-apps.spreadsheet": "text/csv",
            "application/vnd.google-apps.presentation": "text/plain",
        }

        # Check if image
        is_image = mime_type.startswith("image/")

        if mime_type in export_formats:
            # Google Docs format -> export
            export_url = f"https://www.googleapis.com/drive/v3/files/{self.file_id}/export"
            content_response = requests.get(
                export_url,
                headers=headers,
                params={"mimeType": export_formats[mime_type]},
                timeout=REQUEST_TIMEOUT,
            )
            content_response.raise_for_status()
            content = content_response.text
            raw_content = content_response.content
        else:
            # Regular file -> direct download
            download_url = f"https://www.googleapis.com/drive/v3/files/{self.file_id}?alt=media"
            content_response = requests.get(download_url, headers=headers, timeout=REQUEST_TIMEOUT)
            content_response.raise_for_status()
            raw_content = content_response.content
            content = "" if is_image else content_response.text

        # Output based on selected type
        output_type = getattr(self, "output_type", "Message (for LLM)")

        if output_type == "Message (for LLM)" and is_image:
            # Save image to temp file for Message
            ext = mime_type.split("/")[-1] if "/" in mime_type else "jpg"
            temp_path = Path(tempfile.gettempdir()) / f"gdrive_{self.file_id}_{int(time.time())}.{ext}"
            temp_path.write_bytes(raw_content)
            logger.info(f"Image saved to temp file: {temp_path}")

            return Message(
                text=f"Image loaded from Google Drive: {file_name}",
                files=[str(temp_path)],
                sender="Google Drive",
                sender_name="Google Drive Loader",
            )

        if output_type == "Base64 Data URL" and is_image:
            # Return base64 data URL
            image_base64 = base64.b64encode(raw_content).decode("utf-8")
            data_url = f"data:{mime_type};base64,{image_base64}"
            return Data(
                text=data_url,
                data={
                    "file_id": self.file_id,
                    "file_name": file_name,
                    "mime_type": mime_type,
                    "is_image": is_image,
                    "base64": image_base64,
                },
            )

        # Raw Data or non-image files
        return Data(
            text=content,
            data={
                "file_id": self.file_id,
                "file_name": file_name,
                "mime_type": mime_type,
                "is_image": is_image,
            },
        )
