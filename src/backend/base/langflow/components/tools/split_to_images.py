from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.custom.custom_component.split_to_page import BasePageSplitterComponent
from langflow.field_typing import Tool
from langchain.tools import StructuredTool
from langflow.schema.data import Data
from langflow.io import Output
from loguru import logger
from pydantic import BaseModel, Field
from typing import cast

class SplitToImagesComponent(BasePageSplitterComponent, LCToolComponent):
    """Tool for splitting PDFs/TIFFs into individual images and uploading to blob storage."""

    display_name = "Split To Images"
    description = "Split PDFs and TIFFs into individual images and return list of image URLs or base64 strings."
    documentation = "https://docs.langflow.org/components-tools"
    icon = "scissors-line-dashed"
    name = "SplitToImages"

    # Explicitly define inputs from base class
    inputs = BasePageSplitterComponent._base_inputs
    
    # Define outputs
    outputs = [
        Output(display_name="Data", name="data", method="run_model"),
    ]

    def run_model(self) -> Data:
        """Run the model and return list of image URLs as Data."""
        return self.split_files()

    def build_tool(self) -> Tool:
        """Build a LangChain tool for agent integration."""

        class SplitToImagesInput(BaseModel):
            file_urls: list[str] = Field(
                description="List of URLs or file paths to PDF/TIFF/PNG files"
            )
            keep_original_size: bool = Field(default=True)
            base64_only: bool = Field(default=False)
            split_to_pdf: bool = Field(default=False)

        async def split_files_to_images(
            file_urls: list[str],
            keep_original_size: bool = True,
            base64_only: bool = False,
            split_to_pdf: bool = False,
        ) -> dict[str, list[str]]:
            """Split PDF/TIFF files into images or PDFs."""
            self.keep_original_size = keep_original_size
            self.base64_only = base64_only
            self.split_to_pdf = split_to_pdf

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
            description="Split PDF and TIFF files into individual images or PDFs",
            args_schema=SplitToImagesInput,
            coroutine=split_files_to_images,
        ))