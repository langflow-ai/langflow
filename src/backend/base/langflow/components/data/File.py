from pathlib import Path
from typing import Any, Dict

from langflow.base.data.utils import TEXT_FILE_TYPES, parse_text_file_to_record
from langflow.custom import CustomComponent
from langflow.schema import Record


class FileComponent(CustomComponent):
    display_name = "File"
    description = "A generic file loader."
    icon = "file-text"

    def build_config(self) -> Dict[str, Any]:
        return {
            "path": {
                "display_name": "Path",
                "field_type": "file",
                "file_types": TEXT_FILE_TYPES,
                "info": f"Supported file types: {', '.join(TEXT_FILE_TYPES)}",
            },
            "silent_errors": {
                "display_name": "Silent Errors",
                "advanced": True,
                "info": "If true, errors will not raise an exception.",
            },
        }

    def load_file(self, path: str, silent_errors: bool = False) -> Record:
        resolved_path = self.resolve_path(path)
        path_obj = Path(resolved_path)
        extension = path_obj.suffix[1:].lower()
        if extension == "doc":
            raise ValueError("doc files are not supported. Please save as .docx")
        if extension not in TEXT_FILE_TYPES:
            raise ValueError(f"Unsupported file type: {extension}")
        record = parse_text_file_to_record(resolved_path, silent_errors)
        self.status = record if record else "No data"
        return record or Record()

    def build(
        self,
        path: str,
        silent_errors: bool = False,
    ) -> Record:
        record = self.load_file(path, silent_errors)
        self.status = record
        return record
