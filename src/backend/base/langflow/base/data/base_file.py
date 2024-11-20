from abc import abstractmethod, ABC
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable
from zipfile import ZipFile, is_zipfile
import tarfile

from langflow.custom import Component
from langflow.io import BoolInput, FileInput, HandleInput, Output
from langflow.schema import Data

class BaseFileComponent(Component, ABC):
    """Base class for handling file processing components.

    This class provides common functionality for resolving, validating, and
    processing file paths. Child classes must define valid file extensions
    and implement the `process_files` method.
    """

    # Subclasses can override these class variables
    VALID_EXTENSIONS = []  # To be overridden by child classes
    IGNORE_STARTS_WITH = [".", "__MACOSX"]

    SERVER_FILE_PATH_FIELDNAME = "file_path"
    SUPPORTED_BUNDLE_EXTENSIONS = ["zip", "tar", "tgz", "bz2", "gz"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically update FileInput to include valid extensions and bundles
        self._base_inputs[0].file_types = [*self.valid_extensions, *self.SUPPORTED_BUNDLE_EXTENSIONS]
        
        file_types = ", ".join(self.valid_extensions)
        bundles = ", ".join(self.SUPPORTED_BUNDLE_EXTENSIONS)
        self._base_inputs[0].info = (
            f"Supported file extensions: {file_types}; optionally bundled in file extensions: {bundles}"
        )

    _base_inputs = [
        FileInput(
            name="path",
            display_name="Path",
            file_types=[],  # Dynamically set in __init__
            info="",        # Dynamically set in __init__
            required=False,
        ),
        HandleInput(
            name="file_path",
            display_name="Server File Path",
            info=f"Data object with a '{SERVER_FILE_PATH_FIELDNAME}' property pointing to server file.",
            required=False,
            input_types=["Data"],
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            advanced=True,
            info="If true, errors will not raise an exception.",
        ),
        BoolInput(
            name="delete_server_file_after_processing",
            display_name="Delete Server File After Processing",
            advanced=True,
            value=True,
            info="If true, the Server File Path will be deleted after processing.",
        ),
    ]

    _base_outputs = [
        Output(display_name="Data", name="data", method="load_files")
    ]

    @abstractmethod
    def process_files(self, file_list: list[Path]) -> list[Data]:
        """Processes a list of files and returns parsed data.

        Args:
            file_list (list[Path]): A list of file paths to be processed.

        Returns:
            list[Data]: A list of parsed data objects from the processed files.
        """
        pass

    def load_files(self) -> list[Data]:
        """Loads and parses file(s), including unpacked file bundles.

        This method resolves file paths, validates extensions, and delegates
        file processing to the `process_files` method.

        Returns:
            list[Data]: Parsed data from the processed files.

        Raises:
            ValueError: If no valid file is provided or file extensions are unsupported.
        """
        resolved_paths = self._resolve_paths()

        valid_file_paths = [
            path for path, _ in resolved_paths if path.suffix[1:] in self.valid_extensions
        ]

        processed_data = self.process_files(valid_file_paths)

        try:
            return [data for data in processed_data if data]
        finally:
            for path, delete_after_processing in resolved_paths:
                if delete_after_processing and path.exists():
                    path.unlink()

    @property
    def valid_extensions(self) -> list[str]:
        """Returns valid file extensions for the class.

        This property can be overridden by child classes to provide specific
        extensions.

        Returns:
            list[str]: A list of valid file extensions without the leading dot.
        """
        return self.VALID_EXTENSIONS

    @property
    def ignore_starts_with(self) -> list[str]:
        """Returns prefixes to ignore when unpacking file bundles.

        Returns:
            list[str]: A list of prefixes to ignore when unpacking file bundles.
        """
        return self.IGNORE_STARTS_WITH

    def _resolve_paths(self) -> list[tuple[Path, bool]]:
        """Resolves file paths and validates extensions.

        Returns:
            list[tuple[Path, bool]]: Resolved paths and whether they should be removed after processing.

        Raises:
            ValueError: If paths contain unsupported file extensions.
        """
        resolved_paths = []

        def add_path(path: str, to_remove: bool):
            resolved_path = Path(self.resolve_path(path))
            if resolved_path.suffix[1:] not in self.valid_extensions + self.SUPPORTED_BUNDLE_EXTENSIONS:
                msg = f"Unsupported file type: {resolved_path.suffix}"
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)
            else:
                resolved_paths.append((resolved_path, to_remove))

        # Add self.path if provided
        if self.path:
            add_path(self.path, False)

        # Add paths from file_path if provided
        if self.file_path:
            if isinstance(self.file_path, Data):
                self.file_path = [self.file_path]

            if isinstance(self.file_path, list):
                for obj in self.file_path:
                    if not isinstance(obj, Data):
                        msg = f"Unexpected type in file_path. Expected Data, got {type(obj)}."
                        self.log(msg)
                        if not self.silent_errors:
                            raise ValueError(msg)
                        continue

                    server_file_path = obj.data.get(self.SERVER_FILE_PATH_FIELDNAME)
                    if server_file_path:
                        add_path(server_file_path, self.delete_server_file_after_processing)
                    else:
                        msg = f"One of the Data objects is missing the `{self.SERVER_FILE_PATH_FIELDNAME}` property."
                        self.log(msg)
                        if not self.silent_errors:
                            raise ValueError(msg)
            else:
                msg = f"Unexpected type in file_path. Expected list, got {type(self.file_path)}."
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)

        # Unpack file bundles
        final_paths = []
        for path, to_remove in resolved_paths:
            final_paths.append((path, to_remove))
            if path.suffix[1:] in self.SUPPORTED_BUNDLE_EXTENSIONS:
                self.log(f"Unpacking file bundle: {path.name}.")
                final_paths.extend((p, True) for p in self._unpack_file_bundle(path))

        return final_paths

    def _unpack_file_bundle(self, bundle_path: Path) -> list[Path]:
        """Unpacks a file bundle (zip, tar, tgz, etc.) and returns extracted file paths.

        Args:
            bundle_path (Path): Path to the file bundle.

        Returns:
            list[Path]: Paths to the extracted files.

        Raises:
            ValueError: If the bundle contains no valid files or cannot be read.
        """
        unpacked_files = []

        def extract_files(list_files_callable: Callable, extract_file_callable: Callable):
            """Helper to validate and extract files from the bundle."""
            valid_files = [
                file for file in list_files_callable()
                if (
                    any(file.endswith(f".{ext}") for ext in self.valid_extensions)
                    and not file.startswith(tuple(self.IGNORE_STARTS_WITH))
                )
            ]

            if not valid_files:
                msg = f"No valid files in the bundle: {bundle_path.name}."
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)

            for file in valid_files:
                with NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = Path(temp_file.name).with_name(file)
                    file_content = extract_file_callable(file)
                    if file_content:
                        temp_path.write_bytes(file_content.read())
                    unpacked_files.append(temp_path)

        if is_zipfile(bundle_path):
            with ZipFile(bundle_path, "r") as bundle:
                extract_files(
                    list_files_callable=bundle.namelist,
                    extract_file_callable=bundle.open,
                )
        elif tarfile.is_tarfile(bundle_path):
            with tarfile.open(bundle_path, "r:*") as bundle:
                extract_files(
                    list_files_callable=lambda: [
                        member.name for member in bundle.getmembers() if member.isfile()
                    ],
                    extract_file_callable=lambda member_name: bundle.extractfile(
                        next(m for m in bundle.getmembers() if m.name == member_name)
                    ),
                )
        else:
            msg = f"Unsupported bundle format: {bundle_path.suffix}"
            self.log(msg)
            if not self.silent_errors:
                raise ValueError(msg)

        return unpacked_files
