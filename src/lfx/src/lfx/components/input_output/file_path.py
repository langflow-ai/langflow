from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MultilineInput, Output
from lfx.schema.data import Data
from loguru import logger


class FilePathComponent(Component):
    display_name = "File Path"
    category: str = "input_output"
    description = "Load files from server URLs"
    documentation = "http://docs.langflow.org/components/server_file"
    icon = "File"
    name = "File Path"

    # Match the property name expected by FileComponent
    FILE_PATH_FIELD = "file_path"

    inputs = [
        MultilineInput(
            name="file_urls",
            display_name="File URLs",
            required=True,
            info="Enter one or more URLs (one per line) pointing to files on your server",
            placeholder="https://example.com/file1.pdf\nhttps://example.com/file2.pdf",
        ),
        BoolInput(
            name="validate_urls",
            display_name="Validate URLs",
            info="If true, validates that URLs are accessible before returning them",
            value=True,
        ),
        BoolInput(
            name="return_all_urls",
            display_name="Return All URLs",
            info="If true, returns all URLs even if some are invalid",
            value=True,
        ),
    ]

    outputs = [
        Output(
            name="file_path",  # Match the property name expected by FileComponent
            display_name="File Path",
            method="get_file_paths",
        ),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validated_urls: list[str] = []

    async def validate_url(self, url: str) -> bool:
        """Validate that a URL is accessible."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.head(url.strip()) as response:
                    return response.status < 400
        except Exception as e:
            logger.error(f"Error validating URL {url}: {e!s}")
            return False

    async def get_file_paths(self) -> list[Data]:
        """Get file paths for the FileComponent to process."""
        try:
            if not self.file_urls:
                logger.warning("No URLs provided.")
                return []

            # Split URLs by newlines and filter out empty lines
            urls = [url.strip() for url in self.file_urls.split("\n") if url.strip()]
            file_paths = []

            if self.validate_urls:
                # Validate all URLs concurrently
                import asyncio

                validation_tasks = [self.validate_url(url) for url in urls]
                validation_results = await asyncio.gather(*validation_tasks)

                # Pair URLs with their validation results
                valid_urls = [
                    url
                    for url, is_valid in zip(urls, validation_results, strict=False)
                    if is_valid or self.return_all_urls
                ]

                if not valid_urls:
                    logger.warning("No valid URLs found.")
                    return []

                self._validated_urls = valid_urls

                # Create Data objects for each valid URL
                for url in valid_urls:
                    file_paths.append(Data(data={self.FILE_PATH_FIELD: url}))
            else:
                # If no validation required, create Data objects for all URLs
                file_paths = [Data(data={self.FILE_PATH_FIELD: url}) for url in urls]

            if file_paths:
                self.status = file_paths
                logger.info(f"Generated {len(file_paths)} file paths")
                for path in file_paths:
                    logger.debug(f"File path: {path.data.get(self.FILE_PATH_FIELD)}")
            else:
                logger.warning("No file paths generated")

            return file_paths

        except Exception as e:
            logger.error(f"Error in get_file_paths: {e!s}")
            return []

    def build(self) -> list[Data]:
        """Build method to support both async and sync operation."""
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.get_file_paths())
        finally:
            loop.close()
