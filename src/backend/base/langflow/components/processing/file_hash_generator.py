import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from langflow.custom.custom_component.component import Component
from langflow.io import Output, MultilineInput, DropdownInput
from langflow.schema.data import Data
from loguru import logger


class FileHashGeneratorComponent(Component):
    """Component for generating MD5 hashes of files for deduplication.

    This component takes a file path or URL and generates MD5 hash.
    - For URLs: Downloads the file temporarily and hashes the content
    - For local paths: Hashes the file content directly
    """

    display_name = "File Hash Generator"
    description = "Generate MD5 hash for a file (local or URL) to enable deduplication"
    documentation = "https://docs.langflow.org/components-processing"
    icon = "hash"
    name = "FileHashGenerator"
    category = "processing"

    inputs = [
        MultilineInput(
            name="file_data",
            display_name="File Path",
            info="File path or URL to be hashed.",
            tool_mode=True,
        ),
        DropdownInput(
            name="hash_mode",
            display_name="Hash Mode",
            info="'content' to hash file content (downloads URLs), 'url' to hash URL string only (faster)",
            value="content",
            options=["content", "url"],
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Hash Data",
            name="hash_output",
            method="generate_hash",
        ),
    ]

    def _is_url(self, path: str) -> bool:
        """Check if path is a URL."""
        return path.startswith(("http://", "https://"))

    def _get_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        parsed = urlparse(url)
        path = parsed.path

        # Get the last part of the path
        filename = path.split("/")[-1]

        # Remove query parameters from filename if present
        if "?" in filename:
            filename = filename.split("?")[0]

        # If no valid filename, create one from URL hash
        if not filename or "." not in filename:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"file_{url_hash}"

        return filename

    def hash_url_string(self, url: str) -> str:
        """
        Generate MD5 hash of URL string (not content).
        Fast method for URL-based deduplication.

        Args:
            url: The URL string to hash

        Returns:
            MD5 hash as hex string
        """
        return hashlib.md5(url.encode()).hexdigest()

    def hash_file_content(self, file_path: str) -> str:
        """
        Generate MD5 hash of file content.
        For URLs: downloads temporarily and hashes content.
        For local files: hashes content directly.

        Args:
            file_path: Path to file or URL

        Returns:
            MD5 hash as hex string

        Raises:
            FileNotFoundError: If local file doesn't exist
            requests.RequestException: If URL download fails
        """
        if self._is_url(file_path):
            # Download URL content and hash it
            return self._hash_url_content(file_path)
        else:
            # Hash local file content
            return self._hash_local_file(file_path)

    def _hash_local_file(self, file_path: str) -> str:
        """Hash local file content."""
        path_obj = Path(file_path)

        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not path_obj.is_file():
            raise ValueError(f"Not a file: {file_path}")

        md5_hash = hashlib.md5()

        with open(path_obj, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5_hash.update(chunk)

        return md5_hash.hexdigest()

    def _hash_url_content(self, url: str) -> str:
        """Download URL content and hash it."""
        md5_hash = hashlib.md5()

        logger.info(f"Downloading file from URL to generate content hash...")

        # Stream download to avoid loading entire file into memory
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    md5_hash.update(chunk)

        return md5_hash.hexdigest()

    def generate_hash(self) -> Data:
        """
        Generate MD5 hash for the provided file path/URL.

        Returns:
            Data object containing hash information

        Raises:
            ValueError: If no valid file path is provided
        """
        file_path = self.file_data

        if not file_path or not file_path.strip():
            msg = "No file path or URL provided. Please provide a file via 'File Path' input."
            raise ValueError(msg)

        file_path = file_path.strip()
        logger.info(f"Processing file: {file_path} with hash mode: {self.hash_mode}")

        try:
            is_url = self._is_url(file_path)

            # Generate hash based on mode
            if self.hash_mode == "url" and is_url:
                # Fast mode: hash URL string only
                file_hash = self.hash_url_string(file_path)
                hash_type = "url_string"
            else:
                # Content mode: hash actual file content
                file_hash = self.hash_file_content(file_path)
                hash_type = "file_content"

            # Extract filename
            if is_url:
                file_name = self._get_filename_from_url(file_path)
                source_type = "url"
            else:
                file_name = Path(file_path).name
                source_type = "local"

            result = {
                "file_path": file_path,
                "file_name": file_name,
                "hash": file_hash,
                "hash_type": hash_type,
                "source_type": source_type,
                "status": "success",
            }

            logger.info(f"Generated {hash_type} hash for {file_name}: {file_hash}")
            self.status = f"Hash generated: {file_hash[:16]}..."

            return Data(data=result)

        except FileNotFoundError as e:
            logger.error(f"File not found: {file_path}")
            error_result = {
                "file_path": file_path,
                "file_name": (
                    self._get_filename_from_url(file_path)
                    if self._is_url(file_path)
                    else Path(file_path).name
                ),
                "hash": None,
                "status": "error",
                "error": f"File not found: {e}",
            }
            self.status = "Error: File not found"
            return Data(data=error_result)

        except requests.RequestException as e:
            logger.error(f"Error downloading URL {file_path}: {e}")
            error_result = {
                "file_path": file_path,
                "file_name": self._get_filename_from_url(file_path),
                "hash": None,
                "status": "error",
                "error": f"Download failed: {e}",
            }
            self.status = "Error: Download failed"
            return Data(data=error_result)

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            error_result = {
                "file_path": file_path,
                "file_name": (
                    self._get_filename_from_url(file_path)
                    if self._is_url(file_path)
                    else Path(file_path).name
                ),
                "hash": None,
                "status": "error",
                "error": str(e),
            }
            self.status = f"Error: {str(e)}"
            return Data(data=error_result)
