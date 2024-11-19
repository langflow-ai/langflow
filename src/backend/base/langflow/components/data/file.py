from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, is_zipfile

from langflow.base.data.utils import TEXT_FILE_TYPES, parallel_load_data, parse_text_file_to_data
from langflow.custom import Component
from langflow.io import BoolInput, FileInput, IntInput, Output, HandleInput
from langflow.schema import Data


class FileComponent(Component):
    """Handles loading and processing of individual or zipped text files.

    This component supports processing multiple valid files within a zip archive, 
    resolving paths, validating file types, and optionally using multithreading for processing.

    Attributes:
        display_name (str): Display name of the component.
        description (str): Brief description of the component.
        icon (str): Icon representing the component in the UI.
        name (str): Identifier for the component.
        inputs (list): Inputs required by the component, including file paths and processing options.
        outputs (list): Outputs of the component after processing files, returning parsed data.
    """
    display_name = "File"
    description = "Load a file to be used in your project."
    icon = "file-text"
    name = "File"

    SERVER_FILE_PATH_FIELDNAME = "file_path"

    inputs = [
        FileInput(
            name="path",
            display_name="Path",
            file_types=[*TEXT_FILE_TYPES, "zip"],
            info=f"Supported file types: {', '.join([*TEXT_FILE_TYPES, 'zip'])}",
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
            name="use_multithreading",
            display_name="Use Multithreading",
            advanced=True,
            info="If true, parallel processing will be enabled for zip files.",
        ),
        IntInput(
            name="concurrency_multithreading",
            display_name="Multithreading Concurrency",
            advanced=True,
            info="The maximum number of workers to use, if concurrency is enabled",
            value=4,
        ),
        BoolInput(
            name="delete_server_file_after_processing",
            display_name="Delete Server File After Processing",
            advanced=True,
            value=True,
            info="If true, the Server File Path will be deleted after processing.",
        ),
    ]

    outputs = [Output(display_name="Data", name="data", method="load_file")]

    def load_file(self) -> list[Data]:
        """Loads and parses file(s), including unpacked zip files, with optional parallelism.

        This method processes files by resolving paths, validating file extensions, and optionally using
        multithreading. Files within zip archives are unpacked and processed as individual files.

        Raises:
            ValueError: If no valid file is provided, or if file extensions are unsupported.

        Returns:
            list[Data]: A list of parsed data objects from the processed files.
        """
        resolved_paths = self._resolve_paths()

        def process_file(file_path: Path) -> Data:
            try:
                self.log(f"Processing file: {file_path.name}.")
                return self._process_single_file(file_path)
            except FileNotFoundError as e:
                msg = f"File not found: {file_path.name}. Error: {e}"
                self.log(msg)
                if not self.silent_errors:
                    raise e
                return None
            except Exception as e:
                msg = f"Unexpected error processing {file_path.name}: {e}"
                self.log(msg)
                if not self.silent_errors:
                    raise e
                return None

        valid_file_paths = [path for path, _ in resolved_paths if path.suffix in [f".{ext}" for ext in TEXT_FILE_TYPES]]

        if not self.use_multithreading:
            self.log("Processing files sequentially.")
            processed_data = [process_file(path) for path in valid_file_paths if path]
        else:
            self.log(f"Starting parallel processing with max workers: {self.concurrency_multithreading}.")
            processed_data = parallel_load_data(
                valid_file_paths,
                silent_errors=self.silent_errors,
                load_function=process_file,
                max_concurrency=self.concurrency_multithreading,
            )

        # Cleanup and filter results
        try:
            return [data for data in processed_data if data]
        finally:
            for path, delete_after_processing in resolved_paths:
                if delete_after_processing and path.exists():
                    self.log(f"Deleting file: {path.name}.")
                    path.unlink()

    def _process_single_file(self, file_path: Path) -> Data:
        """Processes a single file and returns parsed data.

        This method reads the content of a file, validates its format, and parses it
        into a `Data` object.

        Args:
            file_path (Path): Path to the file to be processed.

        Returns:
            Data: Parsed data from the file.

        Raises:
            ValueError: If the file cannot be parsed or is unsupported.
        """
        data = parse_text_file_to_data(str(file_path), silent_errors=self.silent_errors)
        return data or Data()

    def _resolve_paths(self) -> list[tuple[Path, bool]]:
        """Resolves a file path and validates its extension.

        This method checks whether the file extension is supported (matching TEXT_FILE_TYPES or 'zip').
        It resolves the provided path and logs errors for unsupported file types.

        Args:
            path (str): The input file path to be resolved and validated.

        Returns:
            Path | None: The resolved file path if valid, or None if the file type is unsupported and silent_errors is enabled.

        Raises:
            ValueError: If the file type is unsupported and silent_errors is disabled.
        """
        resolved_paths = []

        def add_path(path: str, to_remove: bool):
            resolved_path = Path(self.resolve_path(path))
            if resolved_path.suffix not in [f".{ext}" for ext in [*TEXT_FILE_TYPES, "zip"]]:
                msg = f"Unsupported file type: {resolved_path.suffix}"
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)
            else:
                resolved_paths.append((resolved_path, to_remove))

        # Add self.path if provided; we do not delete these to preserve original behavior
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

        # Unpack zip files and process valid extensions
        final_paths = []
        for path, to_remove in resolved_paths:
            final_paths.append((path, to_remove))
            if is_zipfile(path):
                self.log(f"Unpacking zip file: {path.name}.")
                # always remove zip file contents after processing
                final_paths.extend((p, True) for p in self._unpack_zip_file(path))

        return final_paths

    def _resolve_and_validate_path(self, path: str) -> Path | None:
        """
        Resolves a given file path and validates its extension.

        Checks if the file extension is supported (matches either TEXT_FILE_TYPES or 'zip').
        Logs a message and optionally raises a ValueError if the file type is unsupported.

        Args:
            path (str): The input file path to resolve and validate.

        Returns:
            Path | None: The resolved file path if valid, or None if the file type is unsupported and silent_errors is enabled.

        Raises:
            ValueError: If the file type is unsupported and silent_errors is False.
        """
        resolved_path = Path(self.resolve_path(path))
        if not any(resolved_path.suffix == f".{ext}" for ext in [*TEXT_FILE_TYPES, '.zip']):
            msg = f"Unsupported file type: {resolved_path.suffix}"
            self.log(msg)
            if not self.silent_errors:
                raise ValueError(msg)
            return None
        return resolved_path

    def _unpack_zip_file(self, zip_path: Path) -> list[Path]:
        """Unpacks a zip file and returns paths to its extracted files.

        This method extracts files from a zip archive, validating their extensions and ignoring
        hidden or unsupported files.

        Args:
            zip_path (Path): The path to the zip file to be unpacked.

        Returns:
            list[Path]: A list of paths to valid files extracted from the zip archive.

        Raises:
            ValueError: If the zip file contains no valid files or cannot be read.
        """
        unpacked_files = []
        with ZipFile(zip_path, "r") as zip_file:
            valid_files = [
                name for name in zip_file.namelist()
                if (
                    any(name.endswith(ext) for ext in TEXT_FILE_TYPES) 
                    and not name.startswith((".", "__MACOSX"))
                )
            ]

            if not valid_files:
                msg = f"No valid files in the zip archive: {zip_path.name}."
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)

            for file_name in valid_files:
                with NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = Path(temp_file.name).with_name(file_name)
                    with zip_file.open(file_name) as file_content:
                        temp_path.write_bytes(file_content.read())
                    unpacked_files.append(temp_path)

        return unpacked_files
