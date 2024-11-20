import shutil
import tarfile
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, is_zipfile

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
        self._base_inputs[
            0
        ].info = f"Supported file extensions: {file_types}; optionally bundled in file extensions: {bundles}"

    _base_inputs = [
        FileInput(
            name="path",
            display_name="Path",
            file_types=[],  # Dynamically set in __init__
            info="",  # Dynamically set in __init__
            required=False,
        ),
        HandleInput(
            name="file_path",
            display_name="Server File Path",
            info=(
                f"Data object with a '{SERVER_FILE_PATH_FIELDNAME}' property pointing to server file. "
                "Supercedes 'Path'. "
            ),
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
        BoolInput(
            name="ignore_unsupported_extensions",
            display_name="Ignore Unsupported Extensions",
            advanced=True,
            value=True,
            info="If true, files with unsupported extensions will not be processed.",
        ),
    ]

    _base_outputs = [Output(display_name="Data", name="data", method="load_files")]

    @abstractmethod
    def process_files(self, file_list: list[Path]) -> list[Data]:
        """Processes a list of files and returns parsed data.

        Args:
            file_list (list[Path]): A list of file paths to be processed.

        Returns:
            list[Data]: A list of parsed data objects from the processed files.
        """

    def load_files(self) -> list[Data]:
        """Loads and parses file(s), including unpacked file bundles.

        This method resolves file paths, validates extensions, and delegates
        file processing to the `process_files` method.

        Returns:
            list[Data]: Parsed data from the processed files.

        Raises:
            ValueError: If no valid file is provided or file extensions are unsupported.
        """
        # List to keep track of temporary directories
        self._temp_dirs = []
        final_files_with_flags = []
        try:
            # Step 1: Validate the provided paths
            paths_with_flags = self._validate_and_resolve_paths()

            # self.log(f"paths_with_flags: {paths_with_flags}")

            # Step 2: Handle bundles recursively
            all_files_with_flags = self._unpack_and_collect_files(paths_with_flags)

            # self.log(f"all_files_with_flags: {all_files_with_flags}")

            # Step 3: Final validation of file types and remove-after-processing markers
            final_files_with_flags = self._filter_and_mark_files(all_files_with_flags)

            # self.log(f"final_files_with_flags: {final_files_with_flags}")

            # Extract just the paths for processing
            valid_file_paths = [path for path, _ in final_files_with_flags]

            # self.log(f"valid_file_paths: {valid_file_paths}")

            processed_data = self.process_files(valid_file_paths)

            return [data for data in processed_data if data]
        finally:
            # Delete temporary directories
            for temp_dir in self._temp_dirs:
                temp_dir.cleanup()

            # Delete files marked for deletion
            for path, delete_after_processing in final_files_with_flags:
                if delete_after_processing and path.exists():
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
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

    def _validate_and_resolve_paths(self) -> list[tuple[Path, bool]]:
        """Validate that all input paths exist and are valid.

        Returns:
            list[tuple[Path, bool]]: A list of valid paths and whether they should be deleted after processing.

        Raises:
            ValueError: If any path does not exist.
        """
        resolved_paths = []

        def add_path(path: str, *, delete_after_processing: bool):
            resolved_path = Path(self.resolve_path(path))
            if not resolved_path.exists():
                msg = f"File or directory not found: {path}"
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)
            resolved_paths.append((resolved_path, delete_after_processing))

        if self.path and not self.file_path:  # Only process self.path if file_path is not provided
            add_path(self.path, delete_after_processing=False)  # Files from self.path are never deleted
        elif self.file_path:
            if isinstance(self.file_path, Data):
                self.file_path = [self.file_path]

            for obj in self.file_path:
                if not isinstance(obj, Data):
                    msg = f"Expected Data object in file_path but got {type(obj)}."
                    self.log(msg)
                    if not self.silent_errors:
                        raise ValueError(msg)
                    continue

                server_file_path = obj.data.get(self.SERVER_FILE_PATH_FIELDNAME)
                if server_file_path:
                    add_path(server_file_path, delete_after_processing=self.delete_server_file_after_processing)
                else:
                    msg = f"Data object missing '{self.SERVER_FILE_PATH_FIELDNAME}' property."
                    self.log(msg)
                    if not self.silent_errors:
                        raise ValueError(msg)

        return resolved_paths

    def _unpack_and_collect_files(self, paths_with_flags: list[tuple[Path, bool]]) -> list[tuple[Path, bool]]:
        """Recursively unpack bundles and collect files.

        Args:
            paths_with_flags (list[tuple[Path, bool]]): List of input paths and their delete-after-processing flags.

        Returns:
            list[tuple[Path, bool]]:
                List of all files after unpacking bundles, along with their delete-after-processing flags.
        """
        collected_files_with_flags = []

        for path, delete_after_processing in paths_with_flags:
            if path.is_dir():
                # Recurse into directories
                collected_files_with_flags.extend(
                    [(sub_path, delete_after_processing) for sub_path in path.rglob("*") if sub_path.is_file()]
                )
            elif path.suffix[1:] in self.SUPPORTED_BUNDLE_EXTENSIONS:
                # Unpack supported bundles
                temp_dir = TemporaryDirectory()
                self._temp_dirs.append(temp_dir)
                temp_dir_path = Path(temp_dir.name)
                self._unpack_bundle(path, temp_dir_path)
                subpaths = list(temp_dir_path.iterdir())
                self.log(f"Unpacked bundle {path.name} into {subpaths}")
                for sub_path in subpaths:
                    if sub_path.is_dir():
                        # Add directory to process its contents later
                        collected_files_with_flags.append((sub_path, delete_after_processing))
                    else:
                        collected_files_with_flags.append((sub_path, delete_after_processing))
            else:
                collected_files_with_flags.append((path, delete_after_processing))

        # Recurse again if any directories or bundles are left in the list
        if any(
            file.is_dir() or file.suffix[1:] in self.SUPPORTED_BUNDLE_EXTENSIONS
            for file, _ in collected_files_with_flags
        ):
            return self._unpack_and_collect_files(collected_files_with_flags)

        return collected_files_with_flags

    def _safe_extract(
        self,
        extract_func: Callable[[Path], None],
        members: list[str],
        output_dir: Path,
        archive_type: str,
    ):
        """Safely extract files from an archive, ensuring no path traversal.

        Args:
            extract_func (Callable): Function to perform the extraction.
            members (list[str]): List of members (file paths) to extract.
            output_dir (Path): Directory where files will be extracted.
            archive_type (str): Type of archive (ZIP or TAR) for logging.

        Raises:
            ValueError: If an attempted path traversal is detected.
        """
        for member in members:
            member_path = output_dir / member
            if not member_path.resolve().is_relative_to(output_dir.resolve()):
                raise ValueError(f"Attempted Path Traversal in {archive_type} File: {member}")
            extract_func(output_dir, member)

    def _unpack_bundle(self, bundle_path: Path, output_dir: Path):
        """Unpack a bundle into a temporary directory.

        Args:
            bundle_path (Path): Path to the bundle.
            output_dir (Path): Directory where files will be extracted.

        Raises:
            ValueError: If the bundle format is unsupported or cannot be read.
        """
        if is_zipfile(bundle_path):
            with ZipFile(bundle_path, "r") as bundle:
                self._safe_extract(
                    lambda output_dir, member: bundle.extract(member, path=output_dir),
                    bundle.namelist(),
                    output_dir,
                    "ZIP",
                )
        elif tarfile.is_tarfile(bundle_path):
            with tarfile.open(bundle_path, "r:*") as bundle:
                self._safe_extract(
                    lambda output_dir, member: bundle.extract(member, path=output_dir),
                    [member.name for member in bundle.getmembers()],
                    output_dir,
                    "TAR",
                )
        else:
            msg = f"Unsupported bundle format: {bundle_path.suffix}"
            self.log(msg)
            if not self.silent_errors:
                raise ValueError(msg)

    def _filter_and_mark_files(self, files_with_flags: list[tuple[Path, bool]]) -> list[tuple[Path, bool]]:
        """Validate file types and mark files for removal.

        Args:
            files_with_flags (list[tuple[Path, bool]]): List of files and their delete-after-processing flags.

        Returns:
            list[tuple[Path, bool]]: Validated files with their remove-after-processing markers.

        Raises:
            ValueError: If unsupported files are encountered and `ignore_unsupported_extensions` is False.
        """
        final_files_with_flags = []
        ignored_files = []

        for file, delete_after_processing in files_with_flags:
            if not file.is_file():
                self.log(f"Not a file: {file.name}")
                continue

            if file.suffix[1:] not in self.valid_extensions:
                if self.ignore_unsupported_extensions:
                    ignored_files.append(file.name)
                    continue
                msg = f"Unsupported file extension: {file.suffix}"
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)

            final_files_with_flags.append((file, delete_after_processing))

        if ignored_files:
            self.log(f"Ignored files: {ignored_files}")

        return final_files_with_flags
