from pathlib import Path

from langflow.base.data.utils import TEXT_FILE_TYPES, parse_text_file_to_data
from langflow.custom import Component
from langflow.io import BoolInput, FileInput, Output
from langflow.schema import Data


class FileComponent(Component):
    display_name = "File"
    description = "A generic file loader."
    icon = "file-text"
    name = "File"

    inputs = [
        FileInput(
            name="path",
            display_name="Path",
            file_types=TEXT_FILE_TYPES,
            info=f"Supported file types: {', '.join(TEXT_FILE_TYPES)}",
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            advanced=True,
            info="If true, errors will not raise an exception.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="load_file"),
    ]

    def load_file(self) -> Data:
        if not self.path:
            msg = "Please, upload a file to use this component."
            raise ValueError(msg)
        resolved_path = self.resolve_path(self.path)
        silent_errors = self.silent_errors

        extension = Path(resolved_path).suffix[1:].lower()

        if extension == "doc":
            msg = "doc files are not supported. Please save as .docx"
            raise ValueError(msg)
        if extension not in TEXT_FILE_TYPES:
            msg = f"Unsupported file type: {extension}"
            raise ValueError(msg)

        data = parse_text_file_to_data(resolved_path, silent_errors=silent_errors)
        self.status = data or "No data"
        return data or Data()
