from langflow.custom import Component
from langflow.io import BoolInput, FileInput, HandleInput
from langflow.schema import Data
from langflow.schema.message import Message

SERVER_FILE_PATH_FIELDNAME = "file_path"


class BaseFileComponent(Component, ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically update FileInput to include valid extensions and bundles

    inputs = [
        FileInput(
            name="path",
            display_name="Path",
            info="Path to the file to load.",
        ),
        HandleInput(
            name="file_path",
            display_name="Server File Path",
            info=(
                f"Data object with a '{SERVER_FILE_PATH_FIELDNAME}' property pointing to server file"
                " or a Message object with a path to the file. Supercedes 'Path' but supports same file types."
            ),
            required=False,
            input_types=["Data", "Message"],
            is_list=True,
            advanced=True,
        ),
        BoolInput(
            name="load_all",
            display_name="Load All",
            info="If true, load all files in the directory.",
            advanced=True,
        ),
    ]

    def resolve_path(self, path: str) -> str:
        """Resolve the path to the file."""
        if not path:
            raise ValueError("Path cannot be empty")
        return str(path)

    def get_file_paths(self) -> list[str]:
        """Get the file paths from the input."""
        file_paths = []
        if self.file_path:
            for file_path in self.file_path:
                if isinstance(file_path, Data):
                    if not hasattr(file_path, SERVER_FILE_PATH_FIELDNAME):
                        raise ValueError(
                            f"Data object must have a '{SERVER_FILE_PATH_FIELDNAME}' property"
                        )
                    file_paths.append(getattr(file_path, SERVER_FILE_PATH_FIELDNAME))
                elif isinstance(file_path, Message):
                    file_paths.append(file_path.content)
                else:
                    raise ValueError(
                        f"file_path must be a Data object with a '{SERVER_FILE_PATH_FIELDNAME}' property"
                        " or a Message object with a path to the file"
                    )

        if self.path:
            file_paths.append(self.resolve_path(self.path))

        return file_paths
