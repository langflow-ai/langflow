import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
from langflow.custom.custom_component.component import Component
from langflow.io import DataInput, Output, StrInput
from langflow.schema.data import Data
from langflow.schema.message import Message
from loguru import logger


class ImageMessageBuilderComponent(Component):
    """Component for creating Message objects with images for vision model processing.

    This component bridges the gap between image sources (like Split to Images) and vision-capable
    language models by creating properly formatted Message objects with image attachments.

    Text prompts should be provided via the Language Model's Input field.
    This component focuses solely on passing images through to the model.
    """

    display_name = "Image Message Builder"
    description = "Build a Message object with images from URLs for vision model processing"
    documentation = "https://docs.langflow.org/components-processing"
    icon = "image-plus"
    name = "ImageMessageBuilder"
    category = "processing"

    inputs = [
        DataInput(
            name="image_data",
            display_name="Image Data",
            info=(
                "Data object containing image URLs (e.g., from Split to Images component). "
                "Supports formats: {'image_urls': [...], 'images': [...], 'file_path': '...'}"
            ),
            required=False,
            is_list=True,
        ),
        StrInput(
            name="image_urls",
            display_name="Image URLs",
            info="Direct list of image URLs (alternative to Image Data input)",
            required=False,
            is_list=True,
        ),
        StrInput(
            name="sender",
            display_name="Sender",
            info="Message sender name",
            value="User",
            advanced=True,
        ),
        StrInput(
            name="sender_name",
            display_name="Sender Name",
            info="Display name for the sender",
            value="User",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Message",
            name="message_output",
            method="build_message",
        ),
    ]

    def __init__(self, **kwargs):
        """Initialize the component with temporary directory for downloads."""
        super().__init__(**kwargs)
        self.temp_dir = tempfile.mkdtemp()
        self._downloaded_files: list[str] = []
        logger.debug(f"Created temp directory: {self.temp_dir}")

    def _extract_image_urls(self, image_data_input: Any) -> list[str]:
        """Extract image URLs from various input formats.

        Supports:
        - Split to Images output format: Data object with 'image_urls', 'images', or 'file_path'
        - Direct URL strings
        - Lists of URLs
        - Data objects with nested structure

        Args:
            image_data_input: Input data in various formats

        Returns:
            List of image URLs
        """
        urls = []

        if not image_data_input:
            return urls

        # Handle list of Data objects or mixed inputs
        if isinstance(image_data_input, (list, tuple)):
            for item in image_data_input:
                urls.extend(self._extract_image_urls(item))
            return urls

        # Handle Data object (from Split to Images or similar)
        if isinstance(image_data_input, Data):
            data_dict = image_data_input.data if hasattr(image_data_input, 'data') else {}

            # Try 'image_urls' field (primary field from Split to Images)
            if 'image_urls' in data_dict:
                image_urls = data_dict['image_urls']
                if isinstance(image_urls, list):
                    urls.extend([url for url in image_urls if url])
                elif image_urls:
                    urls.append(str(image_urls))

            # Try 'images' field (array of Data objects with file_path)
            if 'images' in data_dict:
                images = data_dict['images']
                if isinstance(images, list):
                    for img in images:
                        if isinstance(img, dict) and 'data' in img:
                            img_data = img['data']
                            if isinstance(img_data, dict) and 'file_path' in img_data:
                                file_path = img_data['file_path']
                                if file_path:
                                    urls.append(str(file_path))
                        elif isinstance(img, Data):
                            urls.extend(self._extract_image_urls(img))

            # Try 'file_path' field (single file)
            if 'file_path' in data_dict:
                file_path = data_dict['file_path']
                if file_path and file_path not in urls:
                    urls.append(str(file_path))

            # Try 'path' field as fallback
            if 'path' in data_dict and not urls:
                path = data_dict['path']
                if path:
                    urls.append(str(path))

        # Handle plain string
        elif isinstance(image_data_input, str):
            if image_data_input:
                urls.append(image_data_input)

        # Handle dict
        elif isinstance(image_data_input, dict):
            # Recursively extract from dict
            if 'image_urls' in image_data_input:
                urls.extend(self._extract_image_urls(image_data_input['image_urls']))
            if 'images' in image_data_input:
                urls.extend(self._extract_image_urls(image_data_input['images']))
            if 'file_path' in image_data_input:
                fp = image_data_input['file_path']
                if fp:
                    urls.append(str(fp))

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url and url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    async def _download_image(self, url: str) -> str | None:
        """Download an image from a URL to temporary storage.

        Args:
            url: The URL to download from (supports http, https, and local file paths)

        Returns:
            Local file path if successful, None otherwise
        """
        try:
            # If it's already a local file path, just return it
            if not url.startswith(("http://", "https://")):
                if Path(url).exists():
                    logger.debug(f"Using existing local file: {url}")
                    return url
                logger.warning(f"Local file does not exist: {url}")
                return None

            # Parse URL to get filename
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)

            # Handle URLs without clear filename (use hash of URL)
            if not filename or '.' not in filename:
                import hashlib
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                filename = f"image_{url_hash}.png"

            local_path = os.path.join(self.temp_dir, filename)

            # Download the image
            logger.info(f"Downloading image from {url[:100]}...")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    response.raise_for_status()

                    with open(local_path, "wb") as f:
                        while True:
                            chunk = await response.content.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)

            self._downloaded_files.append(local_path)
            logger.info(f"Successfully downloaded image to {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Error downloading image from {url}: {e!s}")
            return None

    async def _download_all_images(self, urls: list[str]) -> list[str]:
        """Download all images asynchronously.

        Args:
            urls: List of image URLs to download

        Returns:
            List of local file paths for successfully downloaded images
        """
        if not urls:
            return []

        logger.info(f"Downloading {len(urls)} image(s)...")

        # Download all images concurrently
        import asyncio
        download_tasks = [self._download_image(url) for url in urls]
        results = await asyncio.gather(*download_tasks, return_exceptions=True)

        # Filter out None values and exceptions
        local_paths = []
        for result in results:
            if isinstance(result, str) and result:
                local_paths.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Download failed with exception: {result}")

        logger.info(f"Successfully downloaded {len(local_paths)} out of {len(urls)} image(s)")
        return local_paths

    async def build_message(self) -> Message:
        """Build a Message object with images (no text).

        This method:
        1. Extracts image URLs from various input sources
        2. Downloads remote images to local storage
        3. Creates a Message object with images attached (empty text)
        4. Returns the Message ready for vision model processing

        Text prompt should be provided separately via Language Model Input field.

        Returns:
            Message object with images (and empty text)

        Raises:
            ValueError: If no valid images are found
        """

        # Extract image URLs from both input sources
        urls_from_data = self._extract_image_urls(self.image_data)
        urls_from_direct = self.image_urls if self.image_urls else []

        # Combine and deduplicate URLs
        all_urls = list(set(urls_from_data + urls_from_direct))

        if not all_urls:
            msg = "No image URLs provided. Please provide images via 'Image Data' or 'Image URLs' input."
            raise ValueError(msg)

        logger.info(f"Processing {len(all_urls)} image URL(s)")

        # Download all images
        from langflow.utils.async_helpers import run_until_complete
        local_paths = run_until_complete(self._download_all_images(all_urls))

        if not local_paths:
            msg = "Failed to download any images. Please check the URLs and try again."
            raise ValueError(msg)

        # Create Message with images (empty text - will be provided by Language Model Input)
        # The Message class will automatically detect images and convert them to base64
        # when to_lc_message() is called by the Language Model component
        message = Message(
            text="[Images attached]",  # Empty text - text prompt should come from Language Model Input field
            sender=self.sender,
            sender_name=self.sender_name,
            files=local_paths,  # Message will auto-detect images and wrap as Image objects
        )

        logger.info(
            f"Created images-only Message with {len(local_paths)} image(s). "
            "Text prompt should come from Language Model Input. "
            "Images will be automatically converted to base64 for vision model."
        )

        self.status = f"Images-only Message created with {len(local_paths)} image(s)"
        return message

    def _cleanup_temp_files(self):
        """Clean up temporary downloaded files."""
        try:
            for file_path in self._downloaded_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Removed temp file: {file_path}")
            self._downloaded_files.clear()

            # Remove temp directory if empty
            if os.path.exists(self.temp_dir):
                try:
                    os.rmdir(self.temp_dir)
                    logger.debug(f"Removed temp directory: {self.temp_dir}")
                except OSError:
                    # Directory not empty, which is fine
                    pass
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e!s}")

    def __del__(self):
        """Clean up temporary files on component destruction."""
        try:
            self._cleanup_temp_files()
        except Exception:
            # Ignore cleanup errors during destruction
            pass
