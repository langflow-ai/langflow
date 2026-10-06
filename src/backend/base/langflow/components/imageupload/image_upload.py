import base64
from pathlib import Path

from langflow.custom import Component
from langflow.io import FileInput, Output
from langflow.schema import Data


class ImageUploadComponent(Component):
    """Component for uploading and encoding images as Base64."""

    display_name = "Image Upload"
    description = "Uploads an image and encodes it in Base64 format."
    icon = "image"
    name = "ImageUploadComponent"

    inputs = [
        FileInput(
            name="image_path",
            display_name="Upload Image",
            file_types=["jpg", "jpeg", "png", "bmp"],
            info="Supported formats: JPG, JPEG, PNG, BMP.",
        )
    ]

    outputs = [
        Output(display_name="Base64 Output", name="base64_output", method="encode_image"),
    ]

    def encode_image(self) -> Data:
        """Reads the uploaded image and encodes it as Base64."""
        if not self.image_path:
            error_message = "No image uploaded. Please upload an image."
            raise ValueError(error_message)

        image_path = Path(self.resolve_path(self.image_path))

        try:
            # Open the image and convert to Base64
            with image_path.open("rb") as img_file:
                base64_encoded = base64.b64encode(img_file.read()).decode("utf-8")

            self.log(f"Successfully encoded image: {image_path.name}")
            return Data(value=base64_encoded)
        except Exception as e:
            self.log(f"Error encoding image: {e}")
            raise
