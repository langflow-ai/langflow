import io
import os
import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
import base64
from loguru import logger
from PIL import Image

from langflow.custom.custom_component.component import Component
from langflow.io import BoolInput, HandleInput, Output, StrInput
from langflow.schema.data import Data

# Global PyMuPDF availability check
try:
    import fitz  # PyMuPDF

    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    fitz = None

# Make HAS_PYMUPDF available globally for any dynamic imports
globals()["HAS_PYMUPDF"] = HAS_PYMUPDF


class BasePageSplitterComponent(Component):
    """Base class for handling file splitting and image processing components.

    This class provides common functionality for:
    - Downloading files from URLs
    - Splitting PDFs into images or individual PDFs
    - Splitting TIFFs into images
    - Processing PNG images
    - Converting to base64
    - Uploading to blob storage or saving locally

    Child classes can override process_files to add custom processing logic.
    """

    @classmethod
    def create_helper(
        cls, temp_dir: str, silent_errors: bool = False, keep_original_size: bool = True
    ):
        """Factory method to create a helper instance without going through __init__."""
        instance = object.__new__(cls)

        # Set required attributes
        instance.temp_dir = temp_dir
        instance.silent_errors = silent_errors
        instance.keep_original_size = keep_original_size
        instance.store_locally = True
        instance.local_storage_path = None
        instance.base64_only = False
        instance.split_to_pdf = False
        instance._downloaded_files = {}
        instance._local_storage_files = []

        return instance

    class ImageFile:
        """Internal class to represent a processed image file with metadata."""

        def __init__(
            self,
            data: Data | list[Data],
            path: Path,
            image_bytes: bytes | None = None,
            base64_str: str | None = None,
            url: str | None = None,
            *,
            delete_after_processing: bool = False,
            silent_errors: bool = False,
        ):
            self._data = data if isinstance(data, list) else [data]
            self.path = path
            self.image_bytes = image_bytes
            self.base64_str = base64_str
            self.url = url
            self.delete_after_processing = delete_after_processing
            self._silent_errors = silent_errors

        @property
        def data(self) -> list[Data]:
            return self._data or []

        @data.setter
        def data(self, value: Data | list[Data]):
            if isinstance(value, Data):
                self._data = [value]
            elif isinstance(value, list) and all(
                isinstance(item, Data) for item in value
            ):
                self._data = value
            else:
                msg = f"data must be a Data object or a list of Data objects. Got: {type(value)}"
                if not self._silent_errors:
                    raise ValueError(msg)

    # Subclasses can override these class variables
    VALID_EXTENSIONS: list[str] = ["pdf", "tiff", "tif", "png"]
    SERVER_FILE_PATH_FIELDNAME = "file_path"

    _base_inputs = [
        HandleInput(
            name="file_path",
            display_name="File URLs",
            info=(
                "Upload file via URL or local server path. Supports: \n"
                "1. Direct HTTP/HTTPS URLs for remote files\n"
                "2. Local server file paths\n"
                "3. Data objects with file path property\n"
                "4. Message objects containing file paths\n"
                "\nSupported formats: PDF, TIFF, PNG"
            ),
            required=True,
            input_types=["Data", "Message"],
            is_list=True,
        ),
        BoolInput(
            name="base64_only",
            display_name="Base64 Only",
            value=False,
            info="If enabled, only return base64 encoded images without saving to storage",
        ),
        BoolInput(
            name="store_locally",
            display_name="Store Locally",
            value=False,
            info="If enabled, save files to local storage instead of uploading to blob storage (ignored if Base64 Only is enabled)",
        ),
        StrInput(
            name="local_storage_path",
            display_name="Local Storage Path",
            required=False,
            info="Custom path for local storage. If not specified, uses temporary directory (only used when Store Locally is enabled)",
            advanced=True,
        ),
        BoolInput(
            name="split_to_pdf",
            display_name="Split to PDF",
            value=False,
            info="If enabled, split multi-page PDFs into individual single-page PDFs instead of images",
        ),
        StrInput(
            name="storage_account",
            display_name="Storage Account",
            required=False,
            info="Storage Account name (ignored if Base64 Only or Store Locally is enabled)",
            advanced=True,
        ),
        StrInput(
            name="temp_container",
            display_name="Temporary Container",
            required=False,
            info="Temporary container name for storing split images (ignored if Base64 Only or Store Locally is enabled)",
            advanced=True,
        ),
        BoolInput(
            name="keep_original_size",
            display_name="Keep Original Size",
            value=True,
            info="Keep the original image size when splitting",
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            value=False,
            info="Continue processing even if some files fail",
            advanced=True,
        ),
    ]

    _base_outputs = [
        Output(display_name="Image URLs", name="image_urls", method="split_files"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.temp_dir = tempfile.mkdtemp()
        self._downloaded_files = {}
        self._local_storage_files = []  # Track files for cleanup
        self._cleanup_on_exit = True  # Control cleanup behavior

    @classmethod
    def create_helper(
        cls,
        temp_dir: str,
        silent_errors: bool = False,
        keep_original_size: bool = True,
        cleanup_on_exit: bool = False,
    ):
        """Factory method to create a helper instance without going through __init__.

        Args:
            temp_dir: Temporary directory for file storage
            silent_errors: Whether to suppress errors
            keep_original_size: Keep original image size or resize
            cleanup_on_exit: Whether to automatically cleanup files on destruction
        """
        instance = object.__new__(cls)

        # Set required attributes
        instance.temp_dir = temp_dir
        instance.silent_errors = silent_errors
        instance.keep_original_size = keep_original_size
        instance.store_locally = True
        instance.local_storage_path = None
        instance.base64_only = False
        instance.split_to_pdf = False
        instance._downloaded_files = {}
        instance._local_storage_files = []
        instance._cleanup_on_exit = cleanup_on_exit

        return instance

    @property
    def valid_extensions(self) -> list[str]:
        """Returns valid file extensions for the class.

        Returns:
            list[str]: A list of valid file extensions without the leading dot.
        """
        return self.VALID_EXTENSIONS

    def _get_local_storage_directory(self) -> str:
        """Get the local storage directory path.

        Returns:
            str: Path to local storage directory
        """
        if hasattr(self, "local_storage_path") and self.local_storage_path:
            # Use custom path if provided
            storage_path = self.local_storage_path
            # Create directory if it doesn't exist
            os.makedirs(storage_path, exist_ok=True)
            return storage_path
        else:
            # Use temp directory as default
            return self.temp_dir

    def _extract_file_paths(self, file_urls_input: Any) -> list[str]:
        """Extract file paths from various input formats.

        Args:
            file_urls_input: Input containing file paths (can be list, Data, Message, or string)

        Returns:
            list[str]: List of file path strings
        """
        from langflow.schema.message import Message

        file_paths = []

        if isinstance(file_urls_input, (list, tuple)):
            for item in file_urls_input:
                if isinstance(item, Data):
                    # Extract from Data object
                    path = ""
                    if hasattr(item, "text"):
                        path = item.text
                    else:
                        path = item.data.get("file_path") or item.data.get("path")
                    if path:
                        file_paths.append(path)
                elif isinstance(item, Message):
                    # Extract from Message object
                    if item.text:
                        file_paths.append(item.text)
                elif isinstance(item, str):
                    file_paths.append(item)
        elif isinstance(file_urls_input, Data):
            path = file_urls_input.data.get("file_path") or file_urls_input.data.get(
                "path"
            )
            if path:
                if isinstance(path, list):
                    file_paths.extend(path)
                else:
                    file_paths.append(path)
        elif isinstance(file_urls_input, Message):
            if file_urls_input.text:
                file_paths.append(file_urls_input.text)
        elif isinstance(file_urls_input, str):
            file_paths.append(file_urls_input)

        return file_paths

    async def _download_file_from_url(self, url: str) -> str | None:
        """Download a file from a URL.

        Args:
            url: URL to download from

        Returns:
            Local file path if successful, None otherwise
        """
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

    async def _process_png_image(self, file_path: str) -> list[bytes]:
        """Process PNG image and return as a list with single image bytes.

        Args:
            file_path: Path to PNG file

        Returns:
            List containing single PNG image as bytes
        """
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary (in case of RGBA)
                if img.mode in ("RGBA", "LA", "P"):
                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    rgb_img.paste(
                        img,
                        mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None,
                    )
                    img = rgb_img
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                if not self.keep_original_size:
                    # Resize if needed
                    max_size = (800, 800)
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)

                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format="PNG")
                return [img_byte_arr.getvalue()]

        except Exception as e:
            logger.error(f"Error processing PNG image: {e!s}")
            if not self.silent_errors:
                raise
            return []

    async def _split_pdf_to_pdfs(self, file_path: str) -> list[bytes]:
        """Split multi-page PDF into individual single-page PDFs.

        Args:
            file_path: Path to PDF file

        Returns:
            List of PDF bytes, one for each page
        """
        if not HAS_PYMUPDF:
            raise ImportError(
                "PyMuPDF (fitz) is required for PDF processing. Please install PyMuPDF>=1.24.0"
            )

        try:
            pdf_bytes_list = []

            # Open PDF
            pdf_document = fitz.open(file_path)

            for page_num in range(pdf_document.page_count):
                # Create a new PDF with just this page
                new_pdf = fitz.open()
                new_pdf.insert_pdf(pdf_document, from_page=page_num, to_page=page_num)

                # Convert to bytes
                pdf_bytes = new_pdf.tobytes()
                pdf_bytes_list.append(pdf_bytes)

                new_pdf.close()

            pdf_document.close()
            return pdf_bytes_list

        except Exception as e:
            logger.error(f"Error splitting PDF to PDFs: {e!s}")
            if not self.silent_errors:
                raise
            return []

    async def _split_pdf_to_images(self, file_path: str) -> list[bytes]:
        """Split PDF into individual page images.

        Args:
            file_path: Path to PDF file

        Returns:
            List of PNG image bytes, one for each page
        """
        if not HAS_PYMUPDF:
            raise ImportError(
                "PyMuPDF (fitz) is required for PDF processing. Please install PyMuPDF>=1.24.0"
            )

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
        """Split TIFF into individual images.

        Args:
            file_path: Path to TIFF file

        Returns:
            List of PNG image bytes, one for each frame
        """
        try:
            with Image.open(file_path) as img:
                image_bytes_list = []

                for i in range(img.n_frames):
                    img.seek(i)
                    frame = img.copy()

                    if not self.keep_original_size:
                        # Resize if needed
                        max_size = (800, 800)
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
        self, image_bytes: bytes, filename: str, content_type: str = "image/png"
    ) -> str | None:
        """Upload an image or PDF to blob storage and get its signed URL.

        Args:
            image_bytes: Image/PDF bytes to upload
            filename: Name for the file in storage
            content_type: MIME type (default: image/png)

        Returns:
            Signed URL for accessing the uploaded file, or None if failed
        """
        try:
            from langflow.services.deps import get_flexstore_service
            from langflow.services.flexstore.settings import FlexStoreSettings

            flexstore_settings = FlexStoreSettings()
            service = get_flexstore_service()

            # Get upload URL
            upload_url = await service.get_signed_url_upload(
                storage_account=self.storage_account
                or flexstore_settings.DEFAULT_TEMPORARY_STORAGE_ACCOUNT,
                container_name=self.temp_container
                or flexstore_settings.DEFAULT_TEMPORARY_STORAGE_CONTAINER,
                file_name=filename,
            )

            if not upload_url:
                raise ValueError("Failed to get upload URL")

            headers = {
                "x-ms-blob-type": "BlockBlob",
                "Content-Type": content_type,
            }

            # Upload the file
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
                or flexstore_settings.DEFAULT_TEMPORARY_STORAGE_ACCOUNT,
                container_name=self.temp_container
                or flexstore_settings.DEFAULT_TEMPORARY_STORAGE_CONTAINER,
                file_name=filename,
            )

            return read_url

        except Exception as e:
            logger.error(f"Error uploading to blob storage: {e!s}")
            if not self.silent_errors:
                raise
            try:
                logger.warning(
                    "Falling back to local storage due to blob storage error"
                )
                return await self._save_image_locally(image_bytes, filename)
            except Exception as fallback_e:
                logger.error(f"Error in fallback local storage: {fallback_e!s}")
                return None

    async def _save_image_locally(self, image_bytes: bytes, filename: str) -> str:
        """Save image locally and return the file path.

        Args:
            image_bytes: Image/PDF bytes to save
            filename: Name for the file

        Returns:
            file:// URL for local access
        """
        try:
            # Get the appropriate storage directory
            storage_dir = self._get_local_storage_directory()
            local_path = os.path.join(storage_dir, filename)

            with open(local_path, "wb") as f:
                f.write(image_bytes)

            # Track locally saved files for cleanup
            self._local_storage_files.append(local_path)

            logger.info(f"Image saved locally: {local_path}")
            # Return file:// URL for local access
            return f"file://{local_path}"

        except Exception as e:
            logger.error(f"Error saving image locally: {e!s}")
            raise

    async def _generate_base64_from_bytes(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string.

        Args:
            image_bytes: Image/PDF bytes to convert

        Returns:
            Base64 encoded string
        """
        try:
            return base64.b64encode(image_bytes).decode("utf-8")

        except Exception as e:
            logger.error(f"Error generating base64: {e!s}")
            if not self.silent_errors:
                raise
            return ""

    async def _process_files_to_urls(
        self, file_paths: list[str]
    ) -> tuple[list[str], list[str]]:
        """Process files and return flat list of image/PDF URLs and base64 strings.

        Args:
            file_paths: List of file paths or URLs to process

        Returns:
            Tuple of (image_urls, base64_strings)
        """
        all_image_urls = []
        all_image_base64 = []

        for file_path in file_paths:
            try:
                # Download if URL
                local_path = file_path
                if file_path.startswith(("http://", "https://")):
                    downloaded_path = await self._download_file_from_url(file_path)
                    if not downloaded_path:
                        continue
                    local_path = downloaded_path

                # Validate file exists
                if not Path(local_path).exists():
                    logger.warning(f"File not found: {local_path}")
                    continue

                # Determine file extension
                ext = Path(local_path).suffix.lower()

                # Process based on file type and split_to_pdf flag
                if ext == ".pdf" and self.split_to_pdf:
                    # Split PDF into multiple single-page PDFs
                    pdf_bytes_list = await self._split_pdf_to_pdfs(local_path)

                    # Process each PDF
                    for i, pdf_bytes in enumerate(pdf_bytes_list):
                        filename = f"{Path(local_path).stem}_page_{i + 1}.pdf"

                        # Always generate base64
                        base64_str = await self._generate_base64_from_bytes(pdf_bytes)
                        all_image_base64.append(base64_str)

                        # Only save/upload if base64_only is False
                        if not self.base64_only:
                            # Check if we should store locally
                            if self.store_locally:
                                url = await self._save_image_locally(
                                    pdf_bytes, filename
                                )
                            else:
                                url = await self._upload_image_to_blob(
                                    pdf_bytes, filename, "application/pdf"
                                )

                            if url:
                                all_image_urls.append(url)
                            else:
                                all_image_urls.append("")

                elif ext == ".pdf":
                    # Split PDF into images
                    images = await self._split_pdf_to_images(local_path)

                    # Process each image
                    for i, image_bytes in enumerate(images):
                        filename = f"{Path(local_path).stem}_page_{i + 1}.png"

                        # Always generate base64
                        base64_str = await self._generate_base64_from_bytes(image_bytes)
                        all_image_base64.append(base64_str)

                        # Only save/upload if base64_only is False
                        if not self.base64_only:
                            # Check if we should store locally
                            if self.store_locally:
                                url = await self._save_image_locally(
                                    image_bytes, filename
                                )
                            else:
                                url = await self._upload_image_to_blob(
                                    image_bytes, filename, "image/png"
                                )

                            if url:
                                all_image_urls.append(url)
                            else:
                                all_image_urls.append("")

                elif ext in [".tiff", ".tif"]:
                    images = await self._split_tiff_to_images(local_path)

                    # Process each image
                    for i, image_bytes in enumerate(images):
                        filename = f"{Path(local_path).stem}_page_{i + 1}.png"

                        # Always generate base64
                        base64_str = await self._generate_base64_from_bytes(image_bytes)
                        all_image_base64.append(base64_str)

                        # Only save/upload if base64_only is False
                        if not self.base64_only:
                            # Check if we should store locally
                            if self.store_locally:
                                url = await self._save_image_locally(
                                    image_bytes, filename
                                )
                            else:
                                url = await self._upload_image_to_blob(
                                    image_bytes, filename, "image/png"
                                )

                            if url:
                                all_image_urls.append(url)
                            else:
                                all_image_urls.append("")

                elif ext == ".png":
                    images = await self._process_png_image(local_path)

                    # Process the image
                    for image_bytes in images:
                        filename = Path(local_path).name

                        # Always generate base64
                        base64_str = await self._generate_base64_from_bytes(image_bytes)
                        all_image_base64.append(base64_str)

                        # Only save/upload if base64_only is False
                        if not self.base64_only:
                            # Check if we should store locally
                            if self.store_locally:
                                url = await self._save_image_locally(
                                    image_bytes, filename
                                )
                            else:
                                url = await self._upload_image_to_blob(
                                    image_bytes, filename, "image/png"
                                )

                            if url:
                                all_image_urls.append(url)
                            else:
                                all_image_urls.append("")
                else:
                    logger.warning(f"Unsupported file type: {ext}")
                    continue

            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e!s}")
                if not self.silent_errors:
                    raise
                continue

        return all_image_urls, all_image_base64

    def split_files(self) -> Data:
        """Split files and return as Data object with URLs and base64 strings.

        Returns:
            Data: Data object containing image_urls, base64_imgs, and metadata
        """
        from langflow.utils.async_helpers import run_until_complete

        # Extract file paths from input
        file_paths = self._extract_file_paths(self.file_path)

        if not file_paths:
            logger.warning("No valid file paths provided")
            return Data(
                data={
                    "image_urls": [],
                    "images": [],
                    "file_path": None,
                    "count": 0,
                    "base64_imgs": [],
                    "error": "No valid file paths provided",
                }
            )

        # Process files asynchronously
        try:
            image_urls, base_64_imgs = run_until_complete(
                self._process_files_to_urls(file_paths)
            )

            # Clean up temp files (but not local storage files)
            self._cleanup_temp_files()

            # Return Data based on mode
            if image_urls or base_64_imgs:
                if self.base64_only:
                    output_type = "PDFs" if self.split_to_pdf else "images"
                    status_msg = f"Generated {len(base_64_imgs)} base64 {output_type} from {len(file_paths)} files"
                    result_data = Data(
                        data={
                            "image_urls": [],
                            "images": [],
                            "file_path": None,
                            "count": len(base_64_imgs),
                            "base64_imgs": base_64_imgs,
                            "base64_only": True,
                            "split_to_pdf": self.split_to_pdf,
                            "stored_locally": False,
                        }
                    )
                else:
                    output_type = "PDFs" if self.split_to_pdf else "images"
                    storage_location = (
                        "local storage" if self.store_locally else "blob storage"
                    )
                    status_msg = f"Generated {len(image_urls)} {output_type} from {len(file_paths)} files in {storage_location}"
                    image_data_objects = [
                        Data(data={"file_path": url}) for url in image_urls
                    ]
                    result_data = Data(
                        data={
                            "image_urls": image_urls,
                            "images": image_data_objects,
                            "file_path": image_urls[0] if image_urls else None,
                            "count": len(base_64_imgs),
                            "base64_imgs": base_64_imgs,
                            "base64_only": False,
                            "split_to_pdf": self.split_to_pdf,
                            "stored_locally": self.store_locally,
                        }
                    )

                self.status = status_msg
                return result_data
            else:
                result_data = Data(
                    data={
                        "image_urls": [],
                        "images": [],
                        "file_path": None,
                        "count": 0,
                        "base64_imgs": [],
                        "error": "No images generated",
                    }
                )
                self.status = "No images generated"
                return result_data

        except Exception as e:
            logger.error(f"Error in split_files: {e!s}")
            self._cleanup_temp_files()
            if not self.silent_errors:
                raise
            return Data(
                data={
                    "image_urls": [],
                    "images": [],
                    "file_path": None,
                    "count": 0,
                    "base64_imgs": [],
                    "error": str(e),
                }
            )

    def cleanup_local_files(self):
        """Clean up locally stored files that were created during processing."""
        cleaned_count = 0
        try:
            for file_path in self._local_storage_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Deleted local file: {file_path}")
                        cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Could not delete file {file_path}: {e}")

            # Clear the list after cleanup
            self._local_storage_files.clear()

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} local file(s)")

        except Exception as e:
            logger.error(f"Error during local file cleanup: {e}")

    def _cleanup_temp_files(self):
        """Clean up temporary files (but preserve local storage files if store_locally is True)."""
        try:
            # Clean up downloaded files
            for file_path in self._downloaded_files.values():
                if os.path.exists(file_path):
                    os.remove(file_path)
            self._downloaded_files.clear()

            # Clean up local storage files if cleanup_on_exit is True
            if self._cleanup_on_exit:
                self.cleanup_local_files()

            # Only clean up temp directory files if NOT storing locally with custom path
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                # If we're storing locally with a custom path, don't clean those files
                if (
                    self.store_locally
                    and hasattr(self, "local_storage_path")
                    and self.local_storage_path
                ):
                    # Only clean temp_dir if it's different from local_storage_path
                    if self.temp_dir != self.local_storage_path:
                        for filename in os.listdir(self.temp_dir):
                            file_path = os.path.join(self.temp_dir, filename)
                            try:
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                            except Exception:
                                pass
                else:
                    # Clean up temp directory if not using local storage or if cleanup_on_exit
                    if not self.store_locally or self._cleanup_on_exit:
                        for filename in os.listdir(self.temp_dir):
                            file_path = os.path.join(self.temp_dir, filename)
                            try:
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                            except Exception:
                                pass

        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e!s}")

    def __del__(self):
        """Clean up temporary files on destruction."""
        try:
            self._cleanup_temp_files()
            # Only remove temp_dir if it exists and is not the custom local storage path
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                if not (
                    self.store_locally
                    and hasattr(self, "local_storage_path")
                    and self.local_storage_path == self.temp_dir
                ):
                    try:
                        os.rmdir(self.temp_dir)
                    except OSError:
                        # Directory not empty or other error, ignore
                        pass
        except Exception:
            pass
