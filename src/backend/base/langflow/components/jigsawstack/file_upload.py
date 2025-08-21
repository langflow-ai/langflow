from pathlib import Path

from langflow.custom.custom_component.component import Component
from langflow.io import BoolInput, FileInput, Output, SecretStrInput, StrInput
from langflow.schema.data import Data


class JigsawStackFileUploadComponent(Component):
    display_name = "File Upload"
    description = "Store any file seamlessly on JigsawStack File Storage and use it in your AI applications. \
        Supports various file types including images, documents, and more."
    documentation = "https://jigsawstack.com/docs/api-reference/store/file/add"
    icon = "JigsawStack"
    name = "JigsawStackFileUpload"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        FileInput(
            name="file",
            display_name="File",
            info="Upload file to be stored on JigsawStack File Storage.",
            required=True,
            file_types=["pdf", "png", "jpg", "jpeg", "mp4", "mp3", "txt", "docx", "xlsx"],
        ),
        StrInput(
            name="key",
            display_name="Key",
            info="The key used to store the file on JigsawStack File Storage. \
                If not provided, a unique key will be generated.",
            required=False,
            tool_mode=True,
        ),
        BoolInput(
            name="overwrite",
            display_name="Overwrite Existing File",
            info="If true, will overwrite the existing file with the same key. \
                If false, will return an error if the file already exists.",
            required=False,
            value=True,
        ),
        BoolInput(
            name="temp_public_url",
            display_name="Return Temporary Public URL",
            info="If true, will return a temporary public URL which lasts for a limited time. \
                If false, will return the file store key which can only be accessed by the owner.",
            required=False,
            value=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="File Store Result", name="file_upload_result", method="upload_file"),
    ]

    def upload_file(self) -> Data:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError as e:
            jigsawstack_import_error = (
                "JigsawStack package not found. Please install it using: pip install jigsawstack>=0.2.7"
            )
            raise ImportError(jigsawstack_import_error) from e

        try:
            client = JigsawStack(api_key=self.api_key)

            file_path = Path(self.file)
            with Path.open(file_path, "rb") as f:
                file_content = f.read()
            params = {}

            if self.key:
                # if key is provided, use it as the file store key
                params["key"] = self.key
            if self.overwrite is not None:
                # if overwrite is provided, use it to determine if the file should be overwritten
                params["overwrite"] = self.overwrite
            if self.temp_public_url is not None:
                # if temp_public_url is provided, use it to determine if a temporary public URL should
                params["temp_public_url"] = self.temp_public_url

            response = client.store.upload(file_content, params)
            return Data(data=response)

        except JigsawStackError as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)
