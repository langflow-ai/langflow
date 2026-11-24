from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data


class JigsawStackObjectDetectionComponent(Component):
    display_name = "Object Detection"
    description = "Perform object detection on images using JigsawStack's Object Detection Model, \
        capable of image grounding, segmentation and computer use."
    documentation = "https://jigsawstack.com/docs/api-reference/ai/object-detection"
    icon = "JigsawStack"
    name = "JigsawStackObjectDetection"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        MessageTextInput(
            name="prompts",
            display_name="Prompts",
            info="The prompts to ground the object detection model. \
                You can pass a list of comma-separated prompts to extract different information from the image.",
            required=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            info="The image URL. Not required if file_store_key is specified.",
            required=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="file_store_key",
            display_name="File Store Key",
            info="The key used to store the image on Jigsawstack File Storage. Not required if url is specified.",
            required=False,
            tool_mode=True,
        ),
        BoolInput(
            name="annotated_image",
            display_name="Return Annotated Image",
            info="If true, will return an url for annotated image with detected objects.",
            required=False,
            value=True,
        ),
        DropdownInput(
            name="features",
            display_name="Features",
            info="Select the features to enable for object detection",
            required=False,
            options=["object_detection", "gui"],
            value=["object_detection", "gui"],
        ),
        DropdownInput(
            name="return_type",
            display_name="Return Type",
            info="Select the return type for the object detection results such as masks or annotations.",
            required=False,
            options=["url", "base64"],
            value="url",
        ),
    ]

    outputs = [
        Output(display_name="Object Detection results", name="object_detection_results", method="detect_objects"),
    ]

    def detect_objects(self) -> Data:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError as e:
            jigsawstack_import_error = (
                "JigsawStack package not found. Please install it using: pip install jigsawstack>=0.2.7"
            )
            raise ImportError(jigsawstack_import_error) from e

        try:
            client = JigsawStack(api_key=self.api_key)

            # build request object
            params = {}
            if self.prompts:
                if isinstance(self.prompts, list):
                    params["prompt"] = self.prompts
                elif isinstance(self.prompts, str):
                    if "," in self.prompts:
                        # Split by comma and strip whitespace
                        params["prompt"] = [p.strip() for p in self.prompts.split(",")]
                    else:
                        params["prompt"] = [self.prompts.strip()]
                else:
                    invalid_prompt_error = "Prompt must be a list of strings or a single string"
                    raise ValueError(invalid_prompt_error)
            if self.url:
                params["url"] = self.url
            if self.file_store_key:
                params["file_store_key"] = self.file_store_key

            # if both url and file_store_key are not provided, raise an error
            if not self.url and not self.file_store_key:
                missing_url_error = "Either URL or File Store Key must be provided to perform object detection"
                raise ValueError(missing_url_error)

            params["annotated_image"] = self.annotated_image
            if self.features:
                params["features"] = self.features

            # Call web scraping
            response = client.vision.object_detection(params)

            if not response.get("success", False):
                failed_response_error = "JigsawStack API returned unsuccessful response"
                raise ValueError(failed_response_error)

            return Data(data=response)

        except JigsawStackError as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)
