"""Autonomize Document Model Component - Unified file/URL-based model component with dropdown selection."""

import asyncio
import concurrent.futures
import mimetypes
import os
import tempfile
import json
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

import aiohttp
from langflow.base.data import BaseFileComponent
from langflow.base.data.utils import IMG_FILE_TYPES
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, Output
from lfx.schema.data import Data
from loguru import logger

from lfx.base.modelhub import ATModelComponent
from langflow.custom.genesis.services.modelhub.model_endpoint import ModelEndpoint


class AutonomizeDocumentModelComponent(ATModelComponent, BaseFileComponent):
    """Unified component for Autonomize document/file-based models with dropdown selection."""

    display_name: str = "Autonomize Document Model"
    description: str = "Unified interface for Autonomize document and image processing models"
    documentation: str = "https://docs.example.com/autonomize-document-models"
    icon: str = "Autonomize"
    name: str = "AutonomizeDocumentModel"
    category: str = "models"
    priority: int = 2  # High priority to appear near top

    # Model mapping for dropdown options
    MODEL_OPTIONS = {
        "SRF Extraction": ModelEndpoint.SRF_EXTRACTION,
        "SRF Identification": ModelEndpoint.SRF_IDENTIFICATION,
        "Letter Split Model": ModelEndpoint.LETTER_SPLIT,
    }

    # Model descriptions for UI
    MODEL_DESCRIPTIONS = {
        "SRF Extraction": "Extract structured retinal findings from medical images",
        "SRF Identification": "Identify subretinal fluid in OCT images",
        "Letter Split Model": "Split documents into logical blocks and sections",
    }

    # Valid file extensions based on model
    MODEL_EXTENSIONS = {
        "SRF Extraction": IMG_FILE_TYPES,
        "SRF Identification": IMG_FILE_TYPES,
        "Letter Split Model": ["pdf", "jpg", "jpeg", "png", "bmp", "tiff", "tif"],
    }

    VALID_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "bmp", "tiff", "tif"]

    inputs = [
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=list(MODEL_OPTIONS.keys()),
            value=list(MODEL_OPTIONS.keys())[0],
            info="Select the Autonomize document model to use",
            real_time_refresh=True,
        ),
        HandleInput(
            name="file_path",
            display_name="Document/Image",
            info=(
                "Upload file via URL or local server path. Supports: \n"
                "1. Direct HTTP/HTTPS URLs for remote files\n"
                "2. Local server file paths\n"
                "3. Data objects with file path property\n"
                "4. Message objects containing file paths\n"
                "\nSupported formats: PDF, JPG, PNG, TIFF, BMP"
            ),
            required=True,
            input_types=["Data", "Message"],
            is_list=True,
        ),
        # Include base file component inputs
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "silent_errors"
        ),
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "delete_server_file_after_processing"
        ),
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "ignore_unsupported_extensions"
        ),
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "ignore_unspecified_files"
        ),
    ]

    outputs = [
        Output(
            name="document_analysis",
            display_name="Document Analysis",
            method="process_document"
        ),
    ]

    def __init__(self, **kwargs):
        ATModelComponent.__init__(self, **kwargs)
        BaseFileComponent.__init__(self, **kwargs)
        self._modelhub_service = None
        self.temp_dir = tempfile.mkdtemp()
        self._downloaded_files = {}
        # Initialize _model_name with the default model endpoint
        self._model_name = self.MODEL_OPTIONS[list(self.MODEL_OPTIONS.keys())[0]]

    @property
    def model_endpoint(self) -> ModelEndpoint:
        """Get the current model endpoint based on selection."""
        return self.MODEL_OPTIONS[self.model_name]

    @property
    def model_name_from_endpoint(self) -> str:
        """Get the model name from the ModelEndpoint."""
        return self.model_endpoint.get_model()

    async def _download_file_from_url(self, url: str) -> str | None:
        """Download a file from a URL."""
        try:
            filename = os.path.basename(urlparse(url).path)
            if not filename:
                filename = "downloaded_file"

            local_path = os.path.join(self.temp_dir, filename)

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    with open(local_path, "wb") as f:
                        while True:
                            chunk = await response.content.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)

            self._downloaded_files[url] = local_path
            logger.info(f"Successfully downloaded file to {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Error downloading file from URL: {e!s}")
            if not self.silent_errors:
                raise
            return None

    async def _validate_and_resolve_paths_async(self) -> list[BaseFileComponent.BaseFile]:
        """Handle URLs and local paths asynchronously."""
        resolved_files = []
        file_paths = self._file_path_as_list()

        for obj in file_paths:
            server_file_path = obj.data.get(self.SERVER_FILE_PATH_FIELDNAME)

            if not server_file_path:
                if not self.ignore_unspecified_files:
                    msg = f"Data object missing '{self.SERVER_FILE_PATH_FIELDNAME}' property."
                    if not self.silent_errors:
                        raise ValueError(msg)
                continue

            try:
                # Handle if server_file_path is a list
                paths_to_process = (
                    server_file_path
                    if isinstance(server_file_path, list)
                    else [server_file_path]
                )

                for path in paths_to_process:
                    try:
                        # Check if it's a URL
                        if isinstance(path, str) and path.startswith(("http://", "https://")):
                            local_path = await self._download_file_from_url(path)
                            if local_path:
                                file_obj = BaseFileComponent.BaseFile(
                                    path=Path(local_path), is_temp=True
                                )
                                resolved_files.append(file_obj)
                        else:
                            # Handle local path
                            path_obj = Path(path) if isinstance(path, str) else path
                            if path_obj.exists():
                                file_obj = BaseFileComponent.BaseFile(
                                    path=path_obj, is_temp=False
                                )
                                resolved_files.append(file_obj)
                            elif not self.silent_errors:
                                raise FileNotFoundError(f"File not found: {path}")

                    except Exception as e:
                        if not self.silent_errors:
                            raise
                        logger.error(f"Error processing path {path}: {e}")

            except Exception as e:
                if not self.silent_errors:
                    raise
                logger.error(f"Error processing file object: {e}")

        return resolved_files

    async def process_files(self, files: List[BaseFileComponent.BaseFile]) -> Dict[str, Any]:
        """Process files using the selected model."""
        results = []

        for file_obj in files:
            file_path = file_obj.path

            # Validate file extension
            valid_extensions = self.MODEL_EXTENSIONS.get(self.model_name, self.VALID_EXTENSIONS)
            file_extension = file_path.suffix.lower().lstrip('.')

            if file_extension not in [ext.lower() for ext in valid_extensions]:
                if not self.ignore_unsupported_extensions:
                    raise ValueError(f"File extension '{file_extension}' not supported by {self.model_name}")
                continue

            try:
                # Use ModelHub service for inference
                # Set the _model_name based on current selection
                self._model_name = self.model_endpoint

                # Get content type
                content_type, _ = mimetypes.guess_type(str(file_path))
                if not content_type:
                    content_type = "application/octet-stream"

                # Special handling for Letter Split Model
                if self.model_name == "Letter Split Model":
                    # For Letter Split Model, we need to process extracted text
                    # This is a placeholder - you may need to integrate with text extraction first
                    response = await self.predict(
                        file_path=file_path,
                        content_type=content_type
                    )
                else:
                    # For SRF models
                    response = await self.predict(
                        file_path=file_path,
                        content_type=content_type
                    )

                # Handle string responses
                if isinstance(response, str):
                    try:
                        response = json.loads(response)
                    except json.JSONDecodeError:
                        response = {"result": response}

                result = {
                    "file_path": str(file_path),
                    "model": self.model_name,
                    "response": response
                }
                results.append(result)

            except Exception as e:
                error_msg = f"Error processing {file_path} with {self.model_name}: {e!s}"
                logger.error(error_msg)
                if not self.silent_errors:
                    raise ValueError(error_msg) from e

                results.append({
                    "file_path": str(file_path),
                    "model": self.model_name,
                    "error": str(e)
                })

        return {
            "model": self.model_name,
            "model_description": self.MODEL_DESCRIPTIONS.get(self.model_name, ""),
            "processed_files": len(results),
            "results": results
        }

    async def process_document(self) -> Data:
        """Process documents using the selected model."""
        try:
            # Resolve file paths (including URLs)
            files = await self._validate_and_resolve_paths_async()

            if not files:
                raise ValueError("No valid files provided for processing")

            # Process files
            results = await self.process_files(files)

            # Clean up temporary files
            if self.delete_server_file_after_processing:
                for file_obj in files:
                    if file_obj.is_temp and file_obj.path.exists():
                        try:
                            file_obj.path.unlink()
                        except Exception as e:
                            logger.warning(f"Failed to delete temporary file {file_obj.path}: {e}")

            data = Data(value=results)
            self.status = f"Processed {len(files)} files with {self.model_name}"
            return data

        except Exception as e:
            error_msg = f"Document processing failed: {e!s}"
            logger.error(error_msg)
            if not self.silent_errors:
                raise ValueError(error_msg) from e

            data = Data(value={"error": str(e), "model": self.model_name})
            self.status = f"Error: {str(e)}"
            return data

    def build(self):
        """Return the main build function for Langflow framework."""
        return self.process_document