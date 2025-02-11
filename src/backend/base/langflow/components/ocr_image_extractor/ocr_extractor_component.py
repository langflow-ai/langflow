import base64
from io import BytesIO
from PIL import Image
import pytesseract
from pathlib import Path

from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema import Data


class ImageDataExtractor(Component):
    """Component for extracting text from an image using OCR (Tesseract)."""

    display_name = "Image Data Extractor (OCR)"
    description = "Decodes a Base64 image and extracts text using OCR."
    icon = "text-recognition"
    name = "ImageDataExtractor"

    inputs = [
        DataInput(
            name="base64_input",
            display_name="Base64 Image Input",
            info="Provide a Base64-encoded image to extract text.",
        )
    ]

    outputs = [
        Output(display_name="Extracted Text", name="extracted_text", method="extract_text")
    ]

    def extract_text(self) -> Message:
        """Decodes Base64 image and extracts text using OCR (Tesseract)."""
        if not self.base64_input:
            raise ValueError("No Base64 input provided.")

        try:
            # Extract the actual Base64 string from Data object
            base64_string = self.base64_input.value  # Extracts the Base64 string

            # Decode Base64 to image
            image_data = base64.b64decode(base64_string)
            image = Image.open(BytesIO(image_data))

            # Extract text using Tesseract OCR
            extracted_text = pytesseract.image_to_string(image)

            self.log(f"OCR Extracted Text: {extracted_text[:100]}...")  # Log first 100 characters
            return Message(value=extracted_text.strip())

        except Exception as e:
            self.log(f"Error extracting text: {e}")
            raise
