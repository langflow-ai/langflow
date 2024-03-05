from typing import Any, Dict, Optional

from langflow import CustomComponent
from langflow.base.data.utils import parse_file_to_record
from langflow.schema import Record


class FileComponent(CustomComponent):
    display_name = "File"
    description = "Load a file."

    def build_config(self) -> Dict[str, Any]:
        return {
            "path": {"display_name": "Path"},
            "silent_errors": {
                "display_name": "Silent Errors",
                "advanced": True,
                "info": "If true, errors will not raise an exception.",
            },
        }

    def build(
        self,
        path: str,
        silent_errors: bool = False,
    ) -> Optional[Record]:
        resolved_path = self.resolve_path(path)
        return parse_file_to_record(resolved_path, silent_errors)
