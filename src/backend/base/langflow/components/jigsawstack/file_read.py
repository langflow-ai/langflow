import tempfile

from langflow.custom.custom_component.component import Component
from langflow.io import Output, SecretStrInput, StrInput
from langflow.schema.data import Data


class JigsawStackFileReadComponent(Component):
    display_name = "File Read"
    description = "Read any previously uploaded file seamlessly from \
        JigsawStack File Storage and use it in your AI applications."
    documentation = "https://jigsawstack.com/docs/api-reference/store/file/get"
    icon = "JigsawStack"
    name = "JigsawStackFileRead"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        StrInput(
            name="key",
            display_name="Key",
            info="The key used to retrieve the file from JigsawStack File Storage.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="File Path", name="file_path", method="read_and_save_file"),
    ]

    def read_and_save_file(self) -> Data:
        """Read file from JigsawStack and save to temp file, return file path."""
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError as e:
            jigsawstack_import_error = (
                "JigsawStack package not found. Please install it using: pip install jigsawstack>=0.2.7"
            )
            raise ImportError(jigsawstack_import_error) from e

        try:
            client = JigsawStack(api_key=self.api_key)
            if not self.key or self.key.strip() == "":
                invalid_key_error = "Key is required to read a file from JigsawStack File Storage."
                raise ValueError(invalid_key_error)

            # Download file content
            response = client.store.get(self.key)

            # Determine file extension
            file_extension = self._detect_file_extension(response)

            # Create temporary file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=file_extension, prefix=f"jigsawstack_{self.key}_"
            ) as temp_file:
                if isinstance(response, bytes):
                    temp_file.write(response)
                else:
                    # Handle string content
                    temp_file.write(response.encode("utf-8"))

                temp_path = temp_file.name

            return Data(
                data={
                    "file_path": temp_path,
                    "key": self.key,
                    "file_extension": file_extension,
                    "size": len(response) if isinstance(response, bytes) else len(str(response)),
                    "success": True,
                }
            )

        except JigsawStackError as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)

    def _detect_file_extension(self, content) -> str:
        """Detect file extension based on content headers."""
        if isinstance(content, bytes):
            # Check magic numbers for common file types
            if content.startswith(b"\xff\xd8\xff"):
                return ".jpg"
            if content.startswith(b"\x89PNG\r\n\x1a\n"):
                return ".png"
            if content.startswith((b"GIF87a", b"GIF89a")):
                return ".gif"
            if content.startswith(b"%PDF"):
                return ".pdf"
            if content.startswith(b"PK\x03\x04"):  # ZIP/DOCX/XLSX
                return ".zip"
            if content.startswith(b"\x00\x00\x01\x00"):  # ICO
                return ".ico"
            if content.startswith(b"RIFF") and b"WEBP" in content[:12]:
                return ".webp"
            if content.startswith((b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
                return ".mp3"
            if content.startswith((b"ftypmp4", b"\x00\x00\x00\x20ftypmp4")):
                return ".mp4"
            # Try to decode as text
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                return ".bin"  # Binary file
        else:
            # String content
            return ".txt"
