import io
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from langflow.base.data import BaseFileComponent

# Handle optional fitz (PyMuPDF) dependency
try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    fitz = None
from lfx.io import BoolInput, HandleInput, Output, StrInput
from lfx.schema.data import Data
from loguru import logger
from PIL import Image

from langflow.custom.genesis.services.deps import get_flexstore_service
from langflow.custom.genesis.services.flexstore.settings import FlexStoreSettings

flexstore_settings = FlexStoreSettings()


class SplitIntoImagesComponent(BaseFileComponent):
    """Component for splitting PDFs/TIFFs into individual images and uploading to blob storage."""

    display_name = "Split Into Images"
    category: str = "helpers"
    description = "Split PDFs and TIFFs into individual images"
    documentation = "http://docs.langflow.org/components/custom"
    icon = "Autonomize"  # You can change this
    name = "split_into_images"

    VALID_EXTENSIONS = ["pdf", "tiff", "tif"]

    inputs = [
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
        HandleInput(
            name="file_path",
            display_name="URL",
            info=(
                "Upload file via URL or local server path. Supports: \n"
                "1. Direct HTTP/HTTPS URLs for remote files\n"
                "2. Local server file paths\n"
                "3. Data objects with file path property\n"
                "4. Message objects containing file paths\n"
                "\nSupports the same file types as the Path input. "
                "Takes precedence over Path input when both are provided."
            ),
            required=False,
            input_types=["Data", "Message"],
            is_list=True,
        ),
        StrInput(
            name="storage_account",
            display_name="Storage Account",
            required=False,
            info="Storage Account name",
            advanced=True,
        ),
        StrInput(
            name="temp_container",
            display_name="Temporary Container",
            required=False,
            info="Temporary container name for storing split images",
            advanced=True,
        ),
        BoolInput(
            name="keep_original_size",
            display_name="Keep Original Size",
            value=True,
            info="Keep the original image size when splitting",
        ),
    ]

    outputs = [
        Output(name="image_urls", display_name="Image URLs", method="get_image_urls")
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.temp_dir = tempfile.mkdtemp()
        self._downloaded_files = {}

    async def _validate_and_resolve_paths_async(
        self,
    ) -> list[BaseFileComponent.BaseFile]:
        """Handle URLs and local paths asynchronously."""
        resolved_files = []
        file_path = self._file_path_as_list()

        for obj in file_path:
            server_file_path = obj.data.get(self.SERVER_FILE_PATH_FIELDNAME)

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
                    local_path = await self._download_file_from_url(server_file_path)
                    if not local_path:
                        continue

                    # Create a new Data object with both the original URL and local path
                    new_data = Data(
                        data={
                            self.SERVER_FILE_PATH_FIELDNAME: local_path,
                            "original_url": server_file_path,
                        }
                    )

                    resolved_files.append(
                        BaseFileComponent.BaseFile(
                            new_data,
                            Path(local_path),
                            delete_after_processing=True,
                        )
                    )
                else:
                    # Handle local files
                    resolved_path = Path(self.resolve_path(str(server_file_path)))
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

        return resolved_files

    async def _download_file_from_url(self, url: str) -> str | None:
        """Download a file from a URL."""
        try:
            filename = os.path.basename(urlparse(url).path)
            if not filename:
                filename = "downloaded_file.pdf"

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

    async def _split_pdf_to_images(self, file_path: str) -> list[bytes]:
        """Split PDF into individual page images."""
        if not FITZ_AVAILABLE:
            raise RuntimeError("PyMuPDF (fitz) is required for PDF processing but is not installed. Install with: pip install PyMuPDF")

        try:
            image_bytes_list = []

            # Open PDF
            pdf_document = fitz.open(file_path)

            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]

                # Get page as an image
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")

                if not self.keep_original_size:
                    # Resize if needed using PIL
                    img = Image.open(io.BytesIO(img_data))
                    max_size = (800, 800)
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)

                    # Convert back to bytes
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format="PNG")
                    img_data = img_byte_arr.getvalue()

                image_bytes_list.append(img_data)

            pdf_document.close()
            return image_bytes_list

        except Exception as e:
            logger.error(f"Error splitting PDF: {e!s}")
            if not self.silent_errors:
                raise
            return []

    async def _split_tiff_to_images(self, file_path: str) -> list[bytes]:
        """Split TIFF into individual images."""
        try:
            with Image.open(file_path) as img:
                image_bytes_list = []

                for i in range(img.n_frames):
                    img.seek(i)
                    frame = img.copy()

                    if not self.keep_original_size:
                        # Resize if needed
                        max_size = (800, 800)  # Example max size
                        frame.thumbnail(max_size, Image.Resampling.LANCZOS)

                    img_byte_arr = io.BytesIO()
                    frame.save(img_byte_arr, format="PNG")
                    image_bytes_list.append(img_byte_arr.getvalue())

                return image_bytes_list

        except Exception as e:
            logger.error(f"Error splitting TIFF: {e!s}")
            if not self.silent_errors:
                raise
            return []

    async def _upload_image_to_blob(
        self, image_bytes: bytes, filename: str
    ) -> str | None:
        """Upload an image to blob storage and get its signed URL."""
        try:
            service = get_flexstore_service()

            # Get upload URL
            upload_url = await service.get_signed_url_upload(
                storage_account=self.storage_account
                or flexstore_settings.DEFAULT_TEMPORARY_STORAGE_ACCOUNT,  # This should be configured
                container_name=self.temp_container
                or flexstore_settings.DEFAULT_TEMPORARY_STORAGE_CONTAINER,
                file_name=filename,
            )

            if not upload_url:
                raise ValueError("Failed to get upload URL")

            headers = {
                "x-ms-blob-type": "BlockBlob",  # Required header for Azure Blob Storage
                "Content-Type": "image/png",  # Since we're saving as PNG
            }

            # Upload the image
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    upload_url,
                    data=image_bytes,
                    headers=headers,
                ) as response:
                    response.raise_for_status()

            # Get read URL
            read_url = await service.get_signed_url(
                storage_account=self.storage_account
                or flexstore_settings.DEFAULT_TEMPORARY_STORAGE_ACCOUNT,  # This should be configured
                container_name=self.temp_container
                or flexstore_settings.DEFAULT_TEMPORARY_STORAGE_CONTAINER,
                file_name=filename,
            )

            return read_url

        except Exception as e:
            logger.error(f"Error uploading image: {e!s}")
            if not self.silent_errors:
                raise
            return None

    def process_files(
        self, file_list: list[BaseFileComponent.BaseFile]
    ) -> list[BaseFileComponent.BaseFile]:
        """Process the files as required by BaseFileComponent"""
        if not file_list:
            msg = "No files to process."
            if not self.silent_errors:
                raise ValueError(msg)
            logger.warning(msg)
        return file_list

    async def _process_files_for_images(
        self, file_list: list[BaseFileComponent.BaseFile]
    ) -> list[Data]:
        """Internal method to process files and generate image URLs."""
        processed_files = []

        for file in file_list:
            try:
                # Split file into images based on type
                ext = file.path.suffix.lower()
                if ext == ".pdf":
                    images = await self._split_pdf_to_images(str(file.path))
                elif ext in [".tiff", ".tif"]:
                    images = await self._split_tiff_to_images(str(file.path))
                else:
                    continue

                # Upload each image and get URLs
                image_urls = []
                for i, image_bytes in enumerate(images):
                    filename = f"{file.path.stem}_page_{i + 1}.png"
                    url = await self._upload_image_to_blob(image_bytes, filename)
                    if url:
                        image_urls.append(url)

                # Create Data object with image URLs
                if image_urls:
                    data = Data(data={"file_path": image_urls})
                    processed_files.append(data)

            except Exception as e:
                logger.error(f"Error processing file {file.path}: {e!s}")
                if not self.silent_errors:
                    raise
                continue

        return processed_files

    async def get_image_urls(self) -> list[Data]:
        """Output method that processes files and returns image URLs."""
        try:
            # Use async validation that handles URLs
            files = await self._validate_and_resolve_paths_async()
            if not files:
                msg = "No valid files provided"
                if not self.silent_errors:
                    raise ValueError(msg)
                return []

            # Process files and get image URLs
            return await self._process_files_for_images(files)

        except Exception as e:
            logger.error(f"Error processing images: {e!s}")
            if not self.silent_errors:
                return []
            raise

    def __del__(self):
        """Clean up temporary files."""
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                for file_path in self._downloaded_files.values():
                    if os.path.exists(file_path):
                        os.remove(file_path)
                os.rmdir(self.temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e!s}")
