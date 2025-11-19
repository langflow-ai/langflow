import io
import os
import tempfile
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import aiohttp
from langchain.tools import StructuredTool
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.io import BoolInput, HandleInput, StrInput
from langflow.schema.data import Data
from loguru import logger
from PIL import Image
from pydantic import BaseModel, Field

from langflow.services.deps import get_flexstore_service
from langflow.services.flexstore.settings import FlexStoreSettings
import base64

# Global PyMuPDF availability check
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    fitz = None

# Make HAS_PYMUPDF available globally for any dynamic imports
globals()['HAS_PYMUPDF'] = HAS_PYMUPDF

flexstore_settings = FlexStoreSettings()


class SplitToImagesInput(BaseModel):
    """Input schema for SplitToImages tool."""

    file_urls: list[str] = Field(
        description="List of URLs or file paths to PDF/TIFF/PNG files to split into images"
    )
    keep_original_size: bool = Field(
        default=True,
        description="Whether to keep original image size or create thumbnails"
    )
    base64_only: bool = Field(
        default=False,
        description="If True, only return base64 encoded images without uploading to storage"
    )
    split_to_pdf: bool = Field(
        default=False,
        description="If True, split multi-page PDFs into individual single-page PDFs instead of images"
    )
    storage_account: str | None = Field(
        default=None,
        description="Azure storage account name (optional, ignored if base64_only=True)"
    )
    temp_container: str | None = Field(
        default=None,
        description="Temporary container name for storing images (optional, ignored if base64_only=True)"
    )


class SplitToImagesComponent(LCToolComponent):
    """Tool for splitting PDFs/TIFFs into individual images and uploading to blob storage."""

    display_name = "Split To Images"
    description = "Split PDFs and TIFFs into individual images and return list of image URLs or base64 strings. Also handles PNG images."
    documentation = "https://docs.langflow.org/components-tools"
    icon = "scissors-line-dashed"
    name = "SplitToImages"

    VALID_EXTENSIONS = ["pdf", "tiff", "tif", "png"]

    inputs = [
        HandleInput(
            name="file_urls",
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
            info="If enabled, only return base64 encoded images without uploading to blob or local storage",
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
            info="Storage Account name (ignored if Base64 Only is enabled)",
            advanced=True,
        ),
        StrInput(
            name="temp_container",
            display_name="Temporary Container",
            required=False,
            info="Temporary container name for storing split images (ignored if Base64 Only is enabled)",
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.temp_dir = tempfile.mkdtemp()
        self._downloaded_files = {}

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

    async def _process_png_image(self, file_path: str) -> list[bytes]:
        """Process PNG image and return as a list with single image bytes."""
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary (in case of RGBA)
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = rgb_img
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

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
        """Split multi-page PDF into individual single-page PDFs."""
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF (fitz) is required for PDF processing. Please install PyMuPDF>=1.24.0")

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
        """Split PDF into individual page images."""
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF (fitz) is required for PDF processing. Please install PyMuPDF>=1.24.0")

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
        """Upload an image or PDF to blob storage and get its signed URL."""
        try:
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
                "x-ms-blob-type": "BlockBlob",  # Required header for Azure Blob Storage
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
            # Only fall back to local storage if silent_errors is enabled
            try:
                logger.warning("Falling back to local storage due to blob storage error")
                return await self._save_image_locally(image_bytes, filename)
            except Exception as fallback_e:
                logger.error(f"Error in fallback local storage: {fallback_e!s}")
                return None

    async def _save_image_locally(self, image_bytes: bytes, filename: str) -> str:
        """Save image locally and return the file path as fallback."""
        try:
            # Save to the temporary directory
            local_path = os.path.join(self.temp_dir, filename)
            with open(local_path, 'wb') as f:
                f.write(image_bytes)

            logger.info(f"Image saved locally: {local_path}")
            # Return file:// URL for local access
            return f"file://{local_path}"

        except Exception as e:
            logger.error(f"Error saving image locally: {e!s}")
            raise

    async def _generate_base64_from_bytes(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string."""
        try:
            return base64.b64encode(image_bytes).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error generating base64: {e!s}")
            if not self.silent_errors:
                raise
            return ""

    def _extract_file_paths(self, file_urls_input: Any) -> list[str]:
        """Extract file paths from various input formats."""
        file_paths = []

        if isinstance(file_urls_input, (list, tuple)):
            for item in file_urls_input:
                if isinstance(item, Data):
                    # Extract from Data object
                    path=""
                    if hasattr(item, "text"):
                        path = item.text
                    else: 
                        path = item.data.get("file_path") or item.data.get("path")
                    file_paths.append(path)
                elif hasattr(item, "text"):
                    # Extract from Message object
                    file_paths.append(item.text)
                elif isinstance(item, str):
                    file_paths.append(item)
        elif isinstance(file_urls_input, Data):
            path = file_urls_input.data.get("file_path") or file_urls_input.data.get("path")
            if path:
                if isinstance(path, list):
                    file_paths.extend(path)
                else:
                    file_paths.append(path)
        elif isinstance(file_urls_input, str):
            file_paths.append(file_urls_input)

        return file_paths

    async def _process_files_to_urls(self, file_paths: list[str]) -> tuple[list[str], list[str]]:
        """Process files and return flat list of image/PDF URLs and base64 strings."""
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
                        
                        # Only upload to storage if base64_only is False
                        if not self.base64_only:
                            url = await self._upload_image_to_blob(pdf_bytes, filename, "application/pdf")
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
                        
                        # Only upload to storage if base64_only is False
                        if not self.base64_only:
                            url = await self._upload_image_to_blob(image_bytes, filename, "image/png")
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
                        
                        # Only upload to storage if base64_only is False
                        if not self.base64_only:
                            url = await self._upload_image_to_blob(image_bytes, filename, "image/png")
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
                        
                        # Only upload to storage if base64_only is False
                        if not self.base64_only:
                            url = await self._upload_image_to_blob(image_bytes, filename, "image/png")
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

    def run_model(self) -> Data:
        """Run the model and return list of image URLs as Data."""
        from langflow.utils.async_helpers import run_until_complete

        # Extract file paths from input
        file_paths = self._extract_file_paths(self.file_urls)

        if not file_paths:
            logger.warning("No valid file paths provided")
            return Data(data={
                "image_urls": [],
                "images": [],
                "file_path": None,
                "count": 0,
                "base64_imgs": [],
                "error": "No valid file paths provided"
            })

        # Process files asynchronously using langflow's async helper
        try:
            image_urls, base_64_imgs = run_until_complete(self._process_files_to_urls(file_paths))

            # Clean up temp files
            self._cleanup_temp_files()

            # Return Data with both formats for maximum compatibility
            if image_urls or base_64_imgs:
                # Determine the status message and what to return based on mode
                if self.base64_only:
                    output_type = "PDFs" if self.split_to_pdf else "images"
                    status_msg = f"Generated {len(base_64_imgs)} base64 {output_type} from {len(file_paths)} files"
                    # Return only base64 data when base64_only is True
                    result_data = Data(
                        data={
                            "image_urls": [],  # Empty when base64_only
                            "images": [],  # Empty when base64_only
                            "file_path": None,  # Empty when base64_only
                            "count": len(base_64_imgs),
                            "base64_imgs": base_64_imgs,
                            "base64_only": True,
                            "split_to_pdf": self.split_to_pdf
                        }
                    )
                else:
                    output_type = "PDFs" if self.split_to_pdf else "images"
                    status_msg = f"Generated {len(image_urls)} {output_type} from {len(file_paths)} files"
                    # Create Data objects for each image with file_path property (for AutonomizeDocumentModel)
                    image_data_objects = [Data(data={"file_path": url}) for url in image_urls]
                    # Return comprehensive data with URLs
                    result_data = Data(
                        data={
                            "image_urls": image_urls,  # URLs when storage is used
                            "images": image_data_objects,  # Data objects for AutonomizeDocumentModel
                            "file_path": image_urls[0] if image_urls else None,  # First image for single-input components
                            "count": len(base_64_imgs),
                            "base64_imgs": base_64_imgs,
                            "base64_only": False,
                            "split_to_pdf": self.split_to_pdf
                        }
                    )
                
                self.status = status_msg
                return result_data
            else:
                # Return empty data if no images generated
                result_data = Data(data={
                    "image_urls": [],
                    "images": [],
                    "file_path": None,
                    "count": 0,
                    "base64_imgs": [],
                    "error": "No images generated"
                })
                self.status = "No images generated"
                return result_data

        except Exception as e:
            logger.error(f"Error in run_model: {e!s}")
            self._cleanup_temp_files()
            if not self.silent_errors:
                raise
            return Data(data={
                "image_urls": [],
                "images": [],
                "file_path": None,
                "count": 0,
                "base64_imgs": [],
                "error": str(e)
            })

    def build_tool(self) -> Tool:
        """Build a LangChain tool for agent integration."""

        async def split_files_to_images(
            file_urls: list[str],
            keep_original_size: bool = True,
            base64_only: bool = False,
            split_to_pdf: bool = False,
            storage_account: str | None = None,
            temp_container: str | None = None,
        ) -> dict[str, list[str]]:
            """Split PDF/TIFF files into individual images or PDFs, or process PNG images and return URLs or base64 strings.

            Args:
                file_urls: List of file URLs or paths to process
                keep_original_size: Whether to keep original size or create thumbnails
                base64_only: If True, only return base64 encoded images without uploading to storage
                split_to_pdf: If True, split multi-page PDFs into individual single-page PDFs instead of images
                storage_account: Azure storage account (optional, ignored if base64_only=True)
                temp_container: Container for temporary storage (optional, ignored if base64_only=True)

            Returns:
                Dict with 'image_urls' and 'base64_imgs' keys containing lists of strings
            """
            # Set instance variables
            self.keep_original_size = keep_original_size
            self.base64_only = base64_only
            self.split_to_pdf = split_to_pdf
            if storage_account and not base64_only:
                self.storage_account = storage_account
            if temp_container and not base64_only:
                self.temp_container = temp_container

            # Process files
            try:
                image_urls, base_64_imgs = await self._process_files_to_urls(file_urls)
                self._cleanup_temp_files()
                return {"image_urls": image_urls, "base64_imgs": base_64_imgs}
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                self._cleanup_temp_files()
                raise

        return cast("Tool", StructuredTool.from_function(
            func=split_files_to_images,
            name="split_to_images",
            description="Split PDF and TIFF files into individual images or PDFs, or process PNG images and return list of URLs or base64 strings. Useful for processing multi-page documents into separate image or PDF files.",
            args_schema=SplitToImagesInput,
            coroutine=split_files_to_images,
        ))

    def _cleanup_temp_files(self):
        """Clean up temporary files."""
        try:
            # Clean up downloaded files
            for file_path in self._downloaded_files.values():
                if os.path.exists(file_path):
                    os.remove(file_path)
            self._downloaded_files.clear()

            # Clean up any files in temp directory (locally saved images)
            # Only clean if not in base64_only mode (no files saved in that mode)
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                import shutil
                for filename in os.listdir(self.temp_dir):
                    file_path = os.path.join(self.temp_dir, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    except Exception:
                        pass  # Ignore individual file cleanup errors
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e!s}")

    def __del__(self):
        """Clean up temporary files on destruction."""
        try:
            self._cleanup_temp_files()
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                os.rmdir(self.temp_dir)
        except Exception:
            # Ignore cleanup errors during destruction
            pass