from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class JigsawStackVOCRComponent(Component):
    display_name = "VOCR"
    description = "Extract data from any document type in a consistent structure with fine-tuned \
        vLLMs for the highest accuracy"
    documentation = "https://jigsawstack.com/docs/api-reference/ai/vocr"
    icon = "JigsawStack"
    name = "JigsawStackVOCR"

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
            info="The prompts used to describe the image. Default prompt is Describe the image in detail. \
                You can pass a list of comma-separated prompts to extract different information from the image.",
            required=False,
            tool_mode=True,
        ),
        StrInput(
            name="url",
            display_name="URL",
            info="The image or document url. Not required if file_store_key is specified.",
            required=False,
            tool_mode=True,
        ),
        StrInput(
            name="file_store_key",
            display_name="File Store Key",
            info="The key used to store the image on Jigsawstack File Storage. Not required if url is specified.",
            required=False,
            tool_mode=True,
        ),
        IntInput(
            name="page_range_start",
            display_name="Page Range",
            info="Page range start limit for the document. If not specified, all pages will be processed.",
            required=False,
        ),
        IntInput(
            name="page_range_end",
            display_name="Page Range End",
            info="Page range end limit for the document. If not specified, all pages will be processed.",
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="VOCR results", name="vocr_results", method="vocr"),
    ]

    def vocr(self) -> Data:
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

            if self.page_range_start and self.page_range_end:
                params["page_range"] = [self.page_range_start, self.page_range_end]

            # Call VOCR
            response = client.vision.vocr(params)

            if not response.get("success", False):
                failed_response_error = "JigsawStack API returned unsuccessful response"
                raise ValueError(failed_response_error)

            return Data(data=response)

        except JigsawStackError as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)
