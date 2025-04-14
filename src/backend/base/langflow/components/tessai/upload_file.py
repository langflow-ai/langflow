import time
from pathlib import Path

import requests

from langflow.custom import Component
from langflow.inputs import BoolInput, FileInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data


class TessAIUploadFileComponent(Component):
    display_name = "Upload File"
    description = "Uploads a file to TessAI platform."
    documentation = "https://docs.tess.pareto.io/"
    icon = "TessAI"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Tess AI API Key",
            info="The API key to use for TessAI.",
            advanced=False,
            input_types=[]
        ),
        FileInput(
            name="file",
            display_name="File",
            info="The file to upload.",
            required=True,
            file_types=[
                "pdf",
                "docx",
                "txt",
                "csv",
                "xlsx",
                "xls",
                "ppt",
                "pptx",
                "png",
                "jpg",
                "jpeg",
                "gif",
                "bmp",
                "tiff",
                "ico",
                "webp",
                "mp3",
                "mp4",
                "wav",
                "webm",
                "m4a",
                "m4v",
                "mov",
                "avi",
                "mkv",
                "webm"
            ],
        ),
        BoolInput(
            name="process",
            display_name="Process File",
            info="Whether to process the file after upload.",
        ),
    ]

    outputs = [Output(display_name="File Data", name="file_data", method="upload_file")]

    BASE_URL = "https://tess.pareto.io/api"

    def upload_file(self) -> Data:
        headers = self._get_headers()
        upload_endpoint = f"{self.BASE_URL}/files"

        try:
            files = {"file": open(Path(self.file), "rb")}
            data = {"process": str(self.process).lower()}

            response = requests.post(upload_endpoint, headers=headers, files=files, data=data)
            response.raise_for_status()
            file_data = response.json()

            if file_data["status"] == "waiting":
                return self._poll_file_status(headers, file_data["id"])

            return Data(data=file_data)
        except requests.RequestException as e:
            raise RuntimeError(f"Error uploading file: {e!s}") from e

    def _get_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _poll_file_status(self, headers: dict, file_id: int) -> dict:
        endpoint = f"{self.BASE_URL}/api/files/{file_id}"
        start_time = time.time()
        timeout = 300

        while time.time() - start_time < timeout:
            try:
                response = requests.get(endpoint, headers=headers)
                response.raise_for_status()
                file_data = response.json()

                if file_data["status"] != "waiting":
                    return file_data

                time.sleep(2)
            except requests.RequestException as e:
                raise RuntimeError(f"Error polling file status: {e!s}") from e

        raise TimeoutError("File processing timed out after 5 minutes")
