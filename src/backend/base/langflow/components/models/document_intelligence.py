"""Azure Document Intelligence Component - Form recognition and document processing."""

import asyncio
import concurrent.futures
import mimetypes
import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import aiohttp
import requests
from langflow.base.data import BaseFileComponent
from langflow.io import BoolInput, DropdownInput, HandleInput, IntInput, Output
from langflow.schema.data import Data
from loguru import logger


class AzureDocumentIntelligenceComponent(BaseFileComponent):
    """Component for Azure Document Intelligence - advanced document processing and form recognition."""

    display_name: str = "Azure Document Intelligence"
    description: str = "Process documents using Azure Document Intelligence (formerly Form Recognizer) for OCR, form extraction, and document analysis"
    documentation: str = "https://docs.microsoft.com/en-us/azure/applied-ai-services/form-recognizer/"
    icon: str = "Azure"
    name: str = "AzureDocumentIntelligence"
    category: str = "models"
    priority: int = 3  # High priority for document processing

    VALID_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "bmp", "tiff", "tif"]

    inputs = [
        HandleInput(
            name="url",
            display_name="URL",
            info="URL to the document to process",
            input_types=["str", "Data", "Message", "list"],
            required=False,
        ),
        # Include only the HandleInput and BoolInputs from base_inputs
        next(
            input
            for input in BaseFileComponent._base_inputs
            if input.name == "file_path"
        ),
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
        DropdownInput(
            name="model_type",
            display_name="Model Type",
            options=["prebuilt-document", "prebuilt-read", "prebuilt-layout"],
            value="prebuilt-document",
            info="Choose the Form Recognizer model to use",
        ),
        BoolInput(
            name="extract_tables",
            display_name="Extract Tables",
            value=True,
            info="Extract and format tables from the document",
        ),
        BoolInput(
            name="include_confidence",
            display_name="Include Confidence Scores",
            value=False,
            advanced=True,
            info="Include confidence scores in the extracted text",
        ),
        BoolInput(
            name="use_multithreading",
            display_name="Use Concurrent Processing",
            value=True,
            info="Enable concurrent processing of multiple files",
        ),
        IntInput(
            name="concurrency_multithreading",
            display_name="Processing Concurrency",
            advanced=True,
            info="Number of files to process concurrently",
            value=2,
        ),
    ]

    outputs = [
        Output(
            display_name="Structured Data", name="structured_data", method="load_files"
        ),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.temp_dir = tempfile.mkdtemp()
        self._downloaded_files = {}
        self._text_content = ""

    def get_text_content(self) -> str:
        """Return the concatenated text content from all processed pages."""
        return self._text_content

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL or generate a default one."""
        try:
            logger.debug(f"Extracting filename from URL: {url}")
            parsed_url = urlparse(url)
            path = unquote(parsed_url.path)
            filename = os.path.basename(path)

            if filename and "." in filename:
                logger.debug(f"Found filename in URL path: {filename}")
                return filename

            response = requests.head(url, allow_redirects=True)
            if "content-disposition" in response.headers:
                content_disp = response.headers["content-disposition"]
                if "filename=" in content_disp:
                    filename = content_disp.split("filename=")[1].strip("\"'")
                    logger.debug(f"Found filename in content-disposition: {filename}")
                    return filename

            if "content-type" in response.headers:
                ext = mimetypes.guess_extension(response.headers["content-type"])
                if ext:
                    filename = f"downloaded{ext}"
                    logger.debug(f"Generated filename from content-type: {filename}")
                    return filename

            logger.debug("Using default filename: downloaded.pdf")
            return "downloaded.pdf"
        except Exception as e:
            logger.error(f"Error extracting filename from URL: {e!s}")
            return "downloaded.pdf"

    async def _download_file_from_url(self, url: str) -> str | None:
        """Download a file from a URL."""
        try:
            logger.debug(f"Attempting to download file from URL: {url}")
            filename = self._extract_filename_from_url(url)
            local_path = os.path.join(self.temp_dir, filename)
            logger.debug(f"Local path for download: {local_path}")

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

    def _extract_url_from_input(self, input_data) -> str | None:
        """Extract URL string from various input types."""
        logger.debug(f"Extracting URL from input data type: {type(input_data)}")

        # Handle list of Data objects (from blob storage)
        if isinstance(input_data, list):
            logger.debug(f"Processing list input with {len(input_data)} items")
            if input_data and isinstance(input_data[0], Data):
                url = input_data[0].data.get("file_path")
                logger.debug(f"Extracted URL from first Data object in list: {url}")
                return url
            return None

        if isinstance(input_data, str):
            logger.debug(f"Input is string: {input_data}")
            return input_data
        elif isinstance(input_data, Data):
            url = (
                input_data.data.get("file_path")
                or input_data.data.get("url")
                or input_data.text
            )
            logger.debug(f"Extracted URL from Data object: {url}")
            return url
        elif hasattr(input_data, "text"):
            logger.debug(f"Extracted URL from text attribute: {input_data.text}")
            return input_data.text
        elif hasattr(input_data, "data"):
            url = (
                input_data.data.get("file_path")
                or input_data.data.get("url")
                or input_data.text
            )
            logger.debug(f"Extracted URL from data attribute: {url}")
            return url
        logger.debug("No URL found in input data")
        return None

    def _validate_and_resolve_paths(self) -> list[BaseFileComponent.BaseFile]:
        """Handle URLs and local paths."""
        resolved_files = []
        logger.debug("Starting path validation and resolution")

        # Handle URL input if provided
        if hasattr(self, "url") and self.url:
            try:
                logger.debug(f"Processing URL input: {self.url}")
                # Extract URL from different input types
                url = self._extract_url_from_input(self.url)
                if not url:
                    logger.warning("No valid URL found in input")
                    return resolved_files

                # Create event loop for async download
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    local_path = loop.run_until_complete(
                        self._download_file_from_url(url)
                    )
                finally:
                    loop.close()

                if local_path:
                    # Create a new Data object with both the original URL and local path
                    new_data = Data(
                        data={
                            self.SERVER_FILE_PATH_FIELDNAME: local_path,
                            "original_url": url,
                        }
                    )
                    logger.debug(
                        f"Created new Data object with local path: {local_path}"
                    )

                    resolved_files.append(
                        BaseFileComponent.BaseFile(
                            new_data,
                            Path(local_path),
                            delete_after_processing=self.delete_server_file_after_processing,
                        )
                    )
            except Exception as e:
                logger.error(f"Error processing URL {url}: {e!s}")
                if not self.silent_errors:
                    raise

        # Handle file_path input
        file_path = self._file_path_as_list()
        logger.debug(f"Processing file_path input: {file_path}")
        for obj in file_path:
            server_file_path = obj.data.get(self.SERVER_FILE_PATH_FIELDNAME)
            logger.debug(f"Processing server file path: {server_file_path}")

            if not server_file_path:
                if not self.ignore_unspecified_files:
                    msg = f"Data object missing '{self.SERVER_FILE_PATH_FIELDNAME}' property."
                    if not self.silent_errors:
                        raise ValueError(msg)
                continue

            try:
                # Check if it's a URL
                if isinstance(server_file_path, str) and server_file_path.startswith(
                    ("http://", "https://")
                ):
                    logger.debug(f"Processing URL from file_path: {server_file_path}")
                    # Create event loop for async download
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        local_path = loop.run_until_complete(
                            self._download_file_from_url(server_file_path)
                        )
                    finally:
                        loop.close()

                    if not local_path:
                        continue

                    # Create a new Data object with both the original URL and local path
                    new_data = Data(
                        data={
                            self.SERVER_FILE_PATH_FIELDNAME: local_path,
                            "original_url": server_file_path,
                        }
                    )
                    logger.debug(
                        f"Created new Data object with local path: {local_path}"
                    )

                    resolved_files.append(
                        BaseFileComponent.BaseFile(
                            new_data,
                            Path(local_path),
                            delete_after_processing=self.delete_server_file_after_processing,
                        )
                    )
                else:
                    # Handle local files
                    resolved_path = Path(self.resolve_path(str(server_file_path)))
                    logger.debug(f"Resolved local file path: {resolved_path}")
                    if not resolved_path.exists():
                        msg = f"File not found: {server_file_path}"
                        if not self.silent_errors:
                            raise ValueError(msg)
                        continue

                    resolved_files.append(
                        BaseFileComponent.BaseFile(
                            obj,
                            resolved_path,
                            delete_after_processing=self.delete_server_file_after_processing,
                        )
                    )

            except Exception as e:
                logger.error(f"Error processing path {server_file_path}: {e!s}")
                if not self.silent_errors:
                    raise
                continue

        logger.debug(f"Resolved {len(resolved_files)} files")
        return resolved_files

    async def process_file(
        self, file_path: str, *, silent_errors: bool = False
    ) -> tuple[Data, str]:
        """Process a single file using the OCR service."""
        try:
            from langflow.services.deps import get_document_intelligence_service
            
            # Create OCR service directly
            ocr_service = get_document_intelligence_service()

            with open(file_path, "rb") as file:
                file_content = file.read()

            extracted_content,plain_text,document_uuid  = await ocr_service.process_document(
                file_content=file_content,
                model_type=self.model_type,
                include_confidence=self.include_confidence,
                extract_tables=self.extract_tables,
            )

            structured_data = Data(
                text=plain_text,
                data={
                    self.SERVER_FILE_PATH_FIELDNAME: str(file_path),
                    "result": extracted_content,
                    "document_uuid":document_uuid
                },
            )

            return structured_data, plain_text

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e!s}")
            if not silent_errors:
                raise
            return None, ""

    def process_files(
        self, file_list: list[BaseFileComponent.BaseFile]
    ) -> list[BaseFileComponent.BaseFile]:
        """Process multiple files with concurrent processing."""
        if not file_list:
            msg = "No files to process."
            raise ValueError(msg)

        concurrency = (
            1
            if not self.use_multithreading
            else max(1, self.concurrency_multithreading)
        )
        file_count = len(file_list)

        logger.info(f"Processing {file_count} files with concurrency: {concurrency}")

        all_plain_text = []
        processed_data = []

        if concurrency > 1 and file_count > 1:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=concurrency
                ) as executor:
                    future_to_file = {
                        executor.submit(
                            lambda path: loop.run_until_complete(
                                self.process_file(
                                    str(path), silent_errors=self.silent_errors
                                )
                            ),
                            file.path,
                        ): file
                        for file in file_list
                    }
                    for future in concurrent.futures.as_completed(future_to_file):
                        try:
                            structured_data, plain_text = future.result()
                            processed_data.append(structured_data)
                            all_plain_text.append(plain_text)
                        except Exception as e:
                            logger.error(f"Error in concurrent processing: {e!s}")
                            if not self.silent_errors:
                                raise
                            processed_data.append(None)
                            all_plain_text.append("")
            finally:
                loop.close()
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                for file in file_list:
                    try:
                        structured_data, plain_text = loop.run_until_complete(
                            self.process_file(
                                str(file.path), silent_errors=self.silent_errors
                            )
                        )
                        processed_data.append(structured_data)
                        all_plain_text.append(plain_text)
                    except Exception as e:
                        logger.error(f"Error processing file {file.path}: {e!s}")
                        if not self.silent_errors:
                            raise
                        processed_data.append(None)
                        all_plain_text.append("")
            finally:
                loop.close()

        # Store concatenated text content
        self._text_content = "\n\n=== NEW DOCUMENT ===\n\n".join(all_plain_text)

        return self.rollup_data(file_list, processed_data)

    def __del__(self):
        """Cleanup temporary files and directory."""
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                # Remove downloaded files
                for file_path in self._downloaded_files.values():
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                # Remove the temporary directory
                os.rmdir(self.temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e!s}")
