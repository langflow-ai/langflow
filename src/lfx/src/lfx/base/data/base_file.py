import ast
import shutil
import tarfile
import threading
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any
from zipfile import ZipFile, is_zipfile

import orjson
import pandas as pd

from lfx.base.data.storage_utils import get_file_size, parse_storage_path, read_file_bytes
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, FileInput, HandleInput, Output, StrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.services.deps import get_settings_service
from lfx.utils.async_helpers import run_until_complete
from lfx.utils.helpers import build_content_type_from_extension

if TYPE_CHECKING:
    from collections.abc import Callable


class BaseFileComponent(Component, ABC):
    """Base class for handling file processing components.

    This class provides common functionality for resolving, validating, and
    processing file paths. Child classes must define valid file extensions
    and implement the `process_files` method.

    # TODO: May want to subclass for local and remote files
    """

    class BaseFile:
        """Internal class to represent a file with additional metadata."""

        def __init__(
            self,
            data: Data | list[Data],
            path: Path,
            *,
            delete_after_processing: bool = False,
            silent_errors: bool = False,
        ):
            self._data = data if isinstance(data, list) else [data]
            self.path = path
            self.delete_after_processing = delete_after_processing
            self._silent_errors = silent_errors

        @property
        def data(self) -> list[Data]:
            return self._data or []

        @data.setter
        def data(self, value: Data | list[Data]):
            if isinstance(value, Data):
                self._data = [value]
            elif isinstance(value, list) and all(isinstance(item, Data) for item in value):
                self._data = value
            else:
                msg = f"data must be a Data object or a list of Data objects. Got: {type(value)}"
                if not self._silent_errors:
                    raise ValueError(msg)

        def merge_data(self, new_data: Data | list[Data] | None) -> list[Data]:
            r"""Generate a new list of Data objects by merging `new_data` into the current `data`.

            Args:
                new_data (Data | list[Data] | None): The new Data object(s) to merge into each existing Data object.
                    If None, the current `data` is returned unchanged.

            Returns:
                list[Data]: A new list of Data objects with `new_data` merged.
            """
            if new_data is None:
                return self.data

            if isinstance(new_data, Data):
                new_data_list = [new_data]
            elif isinstance(new_data, list) and all(isinstance(item, Data) for item in new_data):
                new_data_list = new_data
            else:
                msg = "new_data must be a Data object, a list of Data objects, or None."
                if not self._silent_errors:
                    raise ValueError(msg)
                return self.data

            return [
                Data(data={**data.data, **new_data_item.data}) for data in self.data for new_data_item in new_data_list
            ]

        def __str__(self):
            if len(self.data) == 0:
                text_preview = ""
            elif len(self.data) == 1:
                max_text_length = 50
                text_preview = self.data.get_text()[:max_text_length]
                if len(self.data.get_text()) > max_text_length:
                    text_preview += "..."
                text_preview = f"text_preview='{text_preview}'"
            else:
                text_preview = f"{len(self.data)} data objects"
            return f"BaseFile(path={self.path}, delete_after_processing={self.delete_after_processing}, {text_preview}"

    # Subclasses can override these class variables
    VALID_EXTENSIONS: list[str] = []  # To be overridden by child classes
    IGNORE_STARTS_WITH = [".", "__MACOSX"]

    SERVER_FILE_PATH_FIELDNAME = "file_path"
    SUPPORTED_BUNDLE_EXTENSIONS = ["zip", "tar", "tgz", "bz2", "gz"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Eagerly create the per-instance lock used to serialize load_files_base.
        # Lazy creation inside load_files_base would itself be racy on the very
        # first concurrent entry — two threads could each create their own Lock
        # and bypass serialization on the call this PR is meant to fix.
        self._load_files_base_lock = threading.Lock()
        file_types = [
            *self.valid_extensions,
            *self.SUPPORTED_BUNDLE_EXTENSIONS,
        ]
        supported_file_types = ", ".join(self.valid_extensions)
        bundles = ", ".join(self.SUPPORTED_BUNDLE_EXTENSIONS)
        info = f"Supported file extensions: {supported_file_types}; optionally bundled in file extensions: {bundles}"
        self._update_file_input_metadata(file_types=file_types, info=info)

    def _update_file_input_metadata(self, *, file_types: list[str], info: str) -> None:
        for input_ in self.inputs:
            if isinstance(input_, FileInput) and input_.name == "path":
                input_.file_types = file_types.copy()
                input_.info = info
                break

        mapped_input = self._inputs.get("path")
        if isinstance(mapped_input, FileInput):
            mapped_input.file_types = file_types.copy()
            mapped_input.info = info

    _base_inputs = [
        FileInput(
            name="path",
            display_name="Files",
            fileTypes=[],  # Dynamically set in __init__
            info="",  # Dynamically set in __init__
            required=False,
            list=True,
            value=[],
            tool_mode=True,
        ),
        HandleInput(
            name="file_path",
            display_name="Server File Path",
            info=(
                f"Data object with a '{SERVER_FILE_PATH_FIELDNAME}' property pointing to server file"
                " or a Message object with a path to the file. Supercedes 'Path' but supports same file types."
            ),
            required=False,
            input_types=["Data", "JSON", "Message"],
            is_list=True,
            advanced=True,
        ),
        StrInput(
            name="separator",
            display_name="Separator",
            value="\n\n",
            show=True,
            info="Specify the separator to use between multiple outputs in Message format.",
            advanced=True,
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
        BoolInput(
            name="ignore_unspecified_files",
            display_name="Ignore Unspecified Files",
            advanced=True,
            value=False,
            info=f"If true, Data with no '{SERVER_FILE_PATH_FIELDNAME}' property will be ignored.",
        ),
    ]

    _base_outputs = [
        Output(display_name="Files", name="dataframe", method="load_files"),
    ]

    @abstractmethod
    def process_files(self, file_list: list[BaseFile]) -> list[BaseFile]:
        """Processes a list of files.

        Args:
            file_list (list[BaseFile]): A list of file objects.

        Returns:
            list[BaseFile]: A list of BaseFile objects with updated `data`.
        """

    def _load_files_paths_cache_key(self) -> tuple:
        """Build a stable cache key for ``load_files_base`` from the current inputs.

        The key includes both the local ``path`` input and any server file paths from
        ``file_path``, plus the ``markdown`` flag (which can change which content
        ``process_files`` produces). It is paths-keyed by design so different
        component executions or input changes never reuse another call's cache.
        """
        path_value = getattr(self, "path", None)
        if isinstance(path_value, list):
            paths_part: tuple[str, ...] = tuple(str(p) for p in path_value)
        elif path_value:
            paths_part = (str(path_value),)
        else:
            paths_part = ()

        file_path_part: tuple[str, ...] = ()
        try:
            server_data = self._file_path_as_list()
        except (ValueError, AttributeError):
            server_data = []
        for d in server_data:
            sp = d.data.get(self.SERVER_FILE_PATH_FIELDNAME) if isinstance(d.data, dict) else None
            if sp:
                file_path_part = (*file_path_part, str(sp))

        markdown_flag = getattr(self, "markdown", False)
        return (paths_part, file_path_part, markdown_flag)

    def load_files_base(self) -> list[Data]:
        """Loads and parses file(s), including unpacked file bundles.

        Concurrent output methods on the same component instance are serialized so
        that only one performs the actual file read/process/delete; the others see
        the cached parsed result. This prevents both the spurious ``ValueError``
        from a deleted server file and the silent data-loss interleaving where a
        second caller would otherwise pass validation, then find the file gone in
        ``_filter_and_mark_files`` and produce empty data.

        Returns:
            list[Data]: Parsed data from the processed files.
        """
        cache_key = self._load_files_paths_cache_key()
        paths_subkey = cache_key[:-1]  # paths only, ignoring markdown flag

        with self._load_files_base_lock:
            cache: dict = getattr(self, "_load_files_base_processed_cache", None) or {}

            # Exact-key fast path: same inputs already processed once on this
            # instance — return the cached parsed data and avoid reprocessing
            # (and re-attempting to read a possibly-deleted server file).
            if cache_key in cache:
                return cache[cache_key]

            self._temp_dirs: list[TemporaryDirectory] = []
            self._validate_skipped_due_to_delete_race = False
            final_files: list = []
            try:
                files = self._validate_and_resolve_paths()

                # Recovery path: validation skipped a missing server file marked
                # ``delete_after_processing=True`` (i.e. a prior output call on
                # this same instance already processed and deleted it). If we
                # have any cached parsed result for the same source paths, reuse
                # it so connected outputs see the same content instead of empty
                # data. We accept that the cached entry may have been produced
                # under a different ``markdown`` flag; preserving content is
                # better than silently dropping it.
                if self._validate_skipped_due_to_delete_race and not files and cache:
                    for cached_key, cached_value in cache.items():
                        if cached_key[:-1] == paths_subkey:
                            self.log(
                                "Server file already processed and deleted by a prior call "
                                "on this component instance; reusing cached parsed data."
                            )
                            return cached_value

                all_files = self._unpack_and_collect_files(files)
                final_files = self._filter_and_mark_files(all_files)
                processed_files = self.process_files(final_files)
                result = [data for file in processed_files for data in file.data if file.data]

                # Only cache successful, non-empty results so a legitimate empty
                # input on a later call cannot be misread as a race-recovery hit.
                if result:
                    cache[cache_key] = result
                    self._load_files_base_processed_cache = cache

                return result

            finally:
                # Delete temporary directories
                for temp_dir in self._temp_dirs:
                    temp_dir.cleanup()
                # Delete files marked for deletion
                for file in final_files:
                    if file.delete_after_processing and file.path.exists():
                        if file.path.is_dir():
                            shutil.rmtree(file.path)
                        else:
                            file.path.unlink()

    def load_files_core(self) -> list[Data]:
        """Load files and return as Data objects, with per-instance caching.

        Results are cached keyed by the ``markdown`` attribute so that multiple
        output methods that share the same processing parameters (e.g.
        ``load_files_message`` and ``load_files_dataframe`` when both run with
        ``markdown=False``) do not trigger redundant file processing.

        Returns:
            list[Data]: List of Data objects from all files
        """
        # Use the markdown flag (default False) as the cache key so that
        # structured and markdown outputs are cached independently.
        markdown_flag = getattr(self, "markdown", False)
        cache_attr = f"_load_files_core_cache_{markdown_flag}"
        cache_paths_attr = f"_load_files_core_paths_{markdown_flag}"

        current_paths = tuple(getattr(self, "path", []) or [])
        if hasattr(self, cache_attr) and getattr(self, cache_paths_attr, None) == current_paths:
            return getattr(self, cache_attr)

        data_list = self.load_files_base()
        result = data_list if data_list else [Data()]
        setattr(self, cache_attr, result)
        setattr(self, cache_paths_attr, current_paths)
        return result

    def _extract_file_metadata(self, data_item) -> dict:
        """Extract metadata from a data item with file_path."""
        metadata: dict[str, Any] = {}
        if not hasattr(data_item, "file_path"):
            return metadata

        file_path = data_item.file_path
        file_path_obj = Path(file_path)
        filename = file_path_obj.name

        settings = get_settings_service().settings
        if settings.storage_type == "s3":
            try:
                file_size = get_file_size(file_path)
            except (FileNotFoundError, ValueError):
                # If we can't get file size, set to 0 or omit
                file_size = 0
        else:
            try:
                file_size_stat = file_path_obj.stat()
                file_size = file_size_stat.st_size
            except OSError:
                file_size = 0

        # Basic file metadata
        metadata["file_path"] = file_path
        metadata["filename"] = filename
        metadata["file_size"] = file_size

        # Add MIME type from extension
        extension = filename.split(".")[-1]
        if extension:
            metadata["mimetype"] = build_content_type_from_extension(extension)

        # Copy additional metadata from data if available
        if hasattr(data_item, "data") and isinstance(data_item.data, dict):
            metadata_fields = ["mimetype", "file_size", "created_time", "modified_time"]
            for field in metadata_fields:
                if field in data_item.data:
                    metadata[field] = data_item.data[field]

        return metadata

    def _extract_text(self, data_item) -> str:
        """Extract text content from a data item."""
        if isinstance(data_item.data, dict):
            text = getattr(data_item, "get_text", lambda: None)() or data_item.data.get("text")
            return text if text is not None else str(data_item)
        return str(data_item)

    def load_files_message(self) -> Message:
        """Load files and return as Message.

        Returns:
          Message: Message containing all file data
        """
        data_list = self.load_files_core()
        if not data_list:
            return Message()

        # Extract metadata from the first data item
        metadata = self._extract_file_metadata(data_list[0])

        sep: str = getattr(self, "separator", "\n\n") or "\n\n"
        parts: list[str] = []
        for d in data_list:
            try:
                data_text = self._extract_text(d)
                if data_text and isinstance(data_text, str):
                    parts.append(data_text)
                elif data_text:
                    # get_text() returned non-string, convert it
                    parts.append(str(data_text))
                elif isinstance(d.data, dict):
                    # convert the data dict to a readable string
                    parts.append(orjson.dumps(d.data, option=orjson.OPT_INDENT_2, default=str).decode())
                else:
                    parts.append(str(d))
            except Exception:  # noqa: BLE001
                # Final fallback - just try to convert to string
                # TODO: Consider downstream error case more. Should this raise an error?
                parts.append(str(d))

        return Message(text=sep.join(parts), **metadata)

    def load_files_path(self) -> Message:
        """Returns a Message containing file paths from loaded files.

        Returns:
            Message: Message containing file paths
        """
        files = self._validate_and_resolve_paths()
        settings = get_settings_service().settings

        # For S3 storage, paths are virtual storage keys that don't exist on the local filesystem.
        # Skip the exists() check for S3 files to preserve them in the output.
        # Validation of S3 file existence is deferred until file processing (see _validate_and_resolve_paths).
        # If a file was removed from S3, it will fail when attempting to read/process it later.
        if settings.storage_type == "s3":
            paths = [file.path.as_posix() for file in files]
        else:
            paths = [file.path.as_posix() for file in files if file.path.exists()]

        return Message(text="\n".join(paths) if paths else "")

    def load_files_structured_helper(self, file_path: str) -> list[dict] | None:
        if not file_path:
            return None

        # Get file extension in lowercase
        ext = Path(file_path).suffix.lower()

        settings = get_settings_service().settings

        # For S3 storage, download file bytes first
        if settings.storage_type == "s3":
            # Download file content from S3
            content = run_until_complete(read_file_bytes(file_path))

            # Map file extensions to pandas read functions that support BytesIO
            if ext == ".csv":
                result = pd.read_csv(BytesIO(content))
            elif ext == ".xlsx":
                result = pd.read_excel(BytesIO(content))
            elif ext == ".parquet":
                result = pd.read_parquet(BytesIO(content))
            else:
                return None

            return result.to_dict("records")

        # Local storage - read directly from filesystem
        file_readers: dict[str, Callable[[str], pd.DataFrame]] = {
            ".csv": pd.read_csv,
            ".xlsx": pd.read_excel,
            ".parquet": pd.read_parquet,
            # TODO: sqlite and json support?
        }

        # Get the appropriate reader function or None
        reader = file_readers.get(ext)

        if reader:
            result = reader(file_path)  # MyPy now knows reader is callable
            return result.to_dict("records")

        return None

    def load_files_structured(self) -> DataFrame:
        """Load files and return as DataFrame with structured content.

        Returns:
            DataFrame: DataFrame containing structured content from all files
        """
        data_list = self.load_files_core()
        if not data_list:
            return DataFrame()

        # Get the file path from the first Data object
        file_path = data_list[0].data.get(self.SERVER_FILE_PATH_FIELDNAME, None)

        # If file_path is provided and is a CSV, read it directly
        if file_path and str(file_path).lower().endswith((".csv", ".xlsx", ".parquet")):
            rows = self.load_files_structured_helper(file_path)
        else:
            # Convert Data objects to a list of dictionaries
            # TODO: Parse according to docling standards
            rows = [data_list[0].data]

        result = DataFrame(rows)
        if file_path:
            result.attrs["source_file_path"] = str(file_path)
        self.status = result

        return result

    def parse_string_to_dict(self, s: str) -> dict:
        # Try JSON first (handles true/false/null)
        try:
            result = orjson.loads(s)
            if isinstance(result, dict):
                return result
        except orjson.JSONDecodeError:
            pass

        # Fall back to Python literal evaluation
        try:
            result = ast.literal_eval(s)
            if isinstance(result, dict):
                return result
        except (SyntaxError, ValueError):
            pass

        # If all parsing fails, return the fallback
        return {"value": s}

    def load_files_json(self) -> Data:
        """Load files and return as a single Data object containing JSON content.

        Returns:
            Data: Data object containing JSON content from all files
        """
        data_list = self.load_files_core()
        if not data_list:
            return Data()

        # Grab the JSON data
        json_data = data_list[0].data[data_list[0].text_key]
        json_data = self.parse_string_to_dict(json_data)

        self.status = Data(data=json_data)

        return Data(data=json_data)

    def load_files(self) -> DataFrame:
        """Load files and return as DataFrame.

        Returns:
            DataFrame: DataFrame containing all file data
        """
        data_list = self.load_files_core()
        if not data_list:
            return DataFrame()

        # Convert Data objects to a list of dictionaries
        all_rows = []
        for data in data_list:
            file_path = data.data.get(self.SERVER_FILE_PATH_FIELDNAME)
            row = dict(data.data) if data.data else {}

            # Add text if available, otherwise use the data's text property
            if "text" in data.data:
                row["text"] = data.data["text"]
            if file_path:
                row["file_path"] = file_path
            all_rows.append(row)

        self.status = DataFrame(all_rows)

        return DataFrame(all_rows)

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

    def rollup_data(
        self,
        base_files: list[BaseFile],
        data_list: list[Data | None],
        path_field: str = SERVER_FILE_PATH_FIELDNAME,
    ) -> list[BaseFile]:
        r"""Rolls up Data objects into corresponding BaseFile objects in order given by `base_files`.

        Args:
            base_files (list[BaseFile]): The original BaseFile objects.
            data_list (list[Data | None]): The list of data to be aggregated into the BaseFile objects.
            path_field (str): The field name on the data_list objects that holds the file path as a string.

        Returns:
            list[BaseFile]: A new list of BaseFile objects with merged `data` attributes.
        """

        def _build_data_dict(data_list: list[Data | None], data_list_field: str) -> dict[str, list[Data]]:
            """Builds a dictionary grouping Data objects by a specified field."""
            data_dict: dict[str, list[Data]] = {}
            for data in data_list:
                if data is None:
                    continue
                key = data.data.get(data_list_field)
                if key is None:
                    msg = f"Data object missing required field '{data_list_field}': {data}"
                    self.log(msg)
                    if not self.silent_errors:
                        msg = f"Data object missing required field '{data_list_field}': {data}"
                        self.log(msg)
                        raise ValueError(msg)
                    continue
                data_dict.setdefault(key, []).append(data)
            return data_dict

        # Build the data dictionary from the provided data_list
        data_dict = _build_data_dict(data_list, path_field)

        # Generate the updated list of BaseFile objects, preserving the order of base_files
        updated_base_files = []
        for base_file in base_files:
            new_data_list = data_dict.get(str(base_file.path), [])
            merged_data_list = base_file.merge_data(new_data_list)
            updated_base_files.append(
                BaseFileComponent.BaseFile(
                    data=merged_data_list,
                    path=base_file.path,
                    delete_after_processing=base_file.delete_after_processing,
                )
            )

        return updated_base_files

    def _file_path_as_list(self) -> list[Data]:
        file_path = self.file_path
        if not file_path:
            return []

        def _message_to_data(message: Message) -> Data:
            return Data(**{self.SERVER_FILE_PATH_FIELDNAME: message.text})

        if isinstance(file_path, Data):
            file_path = [file_path]
        elif isinstance(file_path, Message):
            file_path = [_message_to_data(file_path)]
        elif not isinstance(file_path, list):
            msg = f"Expected list of Data objects in file_path but got {type(file_path)}."
            self.log(msg)
            if not self.silent_errors:
                raise ValueError(msg)
            return []

        file_paths = []
        for obj in file_path:
            data_obj = _message_to_data(obj) if isinstance(obj, Message) else obj

            if not isinstance(data_obj, Data):
                msg = f"Expected Data object in file_path but got {type(data_obj)}."
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)
                continue
            file_paths.append(data_obj)

        return file_paths

    def _validate_and_resolve_paths(self) -> list[BaseFile]:
        """Validate that all input paths exist and are valid, and create BaseFile instances.

        Returns:
            list[BaseFile]: A list of valid BaseFile instances.

        Raises:
            ValueError: If any path does not exist.
        """
        resolved_files = []

        def add_file(data: Data, path: str | Path, *, delete_after_processing: bool):
            path_str = str(path)
            settings = get_settings_service().settings

            # When using object storage (S3), file paths are storage keys (e.g., "<flow_id>/<filename>")
            # that don't exist on the local filesystem. We defer validation until file processing.
            # For local storage, validate the file exists immediately to fail fast.
            if settings.storage_type == "s3":
                resolved_files.append(
                    BaseFileComponent.BaseFile(data, Path(path_str), delete_after_processing=delete_after_processing)
                )
            else:
                # Check if path looks like a storage path (flow_id/filename format)
                # If so, use get_full_path to resolve it to the actual storage location
                if parse_storage_path(path_str):
                    try:
                        resolved_path = Path(self.get_full_path(path_str))
                        self.log(f"Resolved storage path '{path_str}' to '{resolved_path}'")
                    except (ValueError, AttributeError) as e:
                        # Fallback to resolve_path if get_full_path fails
                        self.log(f"get_full_path failed for '{path_str}': {e}, falling back to resolve_path")
                        resolved_path = Path(self.resolve_path(path_str))
                else:
                    resolved_path = Path(self.resolve_path(path_str))

                if not resolved_path.exists():
                    if delete_after_processing:
                        # File may have already been processed and deleted by a concurrent output call.
                        # Flag the skip so ``load_files_base`` can recover from any cached
                        # parsed result for these paths instead of returning empty data.
                        self._validate_skipped_due_to_delete_race = True
                        self.log(
                            f"Server file '{path}' not found - skipping as it may have been "
                            "already processed and deleted by a concurrent call."
                        )
                        return
                    msg = f"File not found: '{path}' (resolved to: '{resolved_path}'). Please upload the file again."
                    self.log(msg)
                    if not self.silent_errors:
                        raise ValueError(msg)
                resolved_files.append(
                    BaseFileComponent.BaseFile(data, resolved_path, delete_after_processing=delete_after_processing)
                )

        file_path = self._file_path_as_list()

        if self.path and not file_path:
            # Wrap self.path into a Data object
            if isinstance(self.path, list):
                for path in self.path:
                    data_obj = Data(data={self.SERVER_FILE_PATH_FIELDNAME: path})
                    add_file(data=data_obj, path=path, delete_after_processing=False)
            else:
                data_obj = Data(data={self.SERVER_FILE_PATH_FIELDNAME: self.path})
                add_file(data=data_obj, path=self.path, delete_after_processing=False)
        elif file_path:
            for obj in file_path:
                server_file_path = obj.data.get(self.SERVER_FILE_PATH_FIELDNAME)
                if server_file_path:
                    add_file(
                        data=obj,
                        path=server_file_path,
                        delete_after_processing=self.delete_server_file_after_processing,
                    )
                elif not self.ignore_unspecified_files:
                    msg = f"Data object missing '{self.SERVER_FILE_PATH_FIELDNAME}' property."
                    self.log(msg)
                    if not self.silent_errors:
                        raise ValueError(msg)
                else:
                    msg = f"Ignoring Data object missing '{self.SERVER_FILE_PATH_FIELDNAME}' property:\n{obj}"
                    self.log(msg)

        return resolved_files

    def _unpack_and_collect_files(self, files: list[BaseFile]) -> list[BaseFile]:
        """Recursively unpack bundles and collect files into BaseFile instances.

        Args:
            files (list[BaseFile]): List of BaseFile instances to process.

        Returns:
            list[BaseFile]: Updated list of BaseFile instances.
        """
        collected_files = []

        for file in files:
            path = file.path
            delete_after_processing = file.delete_after_processing
            data = file.data

            if path.is_dir():
                # Recurse into directories. Skip symlinks defensively so that a
                # link planted in a previously-extracted bundle (or a directory
                # the user pointed at) cannot be dereferenced into an arbitrary
                # host file (GHSA-ccv6-r384-xp75).
                collected_files.extend(
                    [
                        BaseFileComponent.BaseFile(
                            data,
                            sub_path,
                            delete_after_processing=delete_after_processing,
                        )
                        for sub_path in path.rglob("*")
                        if sub_path.is_file() and not sub_path.is_symlink()
                    ]
                )
            elif path.suffix[1:] in self.SUPPORTED_BUNDLE_EXTENSIONS:
                # Unpack supported bundles
                temp_dir = TemporaryDirectory()
                self._temp_dirs.append(temp_dir)
                temp_dir_path = Path(temp_dir.name)
                self._unpack_bundle(path, temp_dir_path)
                # Drop any symlink that may have slipped through extraction.
                # `_unpack_bundle` rejects link members for TAR archives, but
                # this guard keeps the contract in place for any future bundle
                # type added to SUPPORTED_BUNDLE_EXTENSIONS.
                subpaths = [p for p in temp_dir_path.iterdir() if not p.is_symlink()]
                self.log(f"Unpacked bundle {path.name} into {subpaths}")
                collected_files.extend(
                    [
                        BaseFileComponent.BaseFile(
                            data,
                            sub_path,
                            delete_after_processing=delete_after_processing,
                        )
                        for sub_path in subpaths
                    ]
                )
            else:
                collected_files.append(file)

        # Recurse again if any directories or bundles are left in the list
        if any(
            file.path.is_dir() or file.path.suffix[1:] in self.SUPPORTED_BUNDLE_EXTENSIONS for file in collected_files
        ):
            return self._unpack_and_collect_files(collected_files)

        return collected_files

    def _unpack_bundle(self, bundle_path: Path, output_dir: Path):
        """Unpack a bundle into a temporary directory.

        Args:
            bundle_path (Path): Path to the bundle.
            output_dir (Path): Directory where files will be extracted.

        Raises:
            ValueError: If the bundle format is unsupported or cannot be read.
        """

        def _safe_extract_zip(bundle: ZipFile, output_dir: Path):
            """Safely extract ZIP files."""
            for member in bundle.namelist():
                # Filter out resource fork information for automatic production of mac
                if Path(member).name.startswith("._"):
                    continue
                member_path = output_dir / member
                # Ensure no path traversal outside `output_dir`
                if not member_path.resolve().is_relative_to(output_dir.resolve()):
                    msg = f"Attempted Path Traversal in ZIP File: {member}"
                    raise ValueError(msg)
                bundle.extract(member, path=output_dir)

        def _safe_extract_tar(bundle: tarfile.TarFile, output_dir: Path):
            """Safely extract TAR files.

            Only regular files and directories are extracted. Symlinks, hardlinks,
            and device/FIFO members are rejected because they could be made to
            point at arbitrary locations on the host filesystem and lead to
            arbitrary file read once the extracted entries are subsequently
            ingested by `process_files()` (GHSA-ccv6-r384-xp75).
            """
            for member in bundle.getmembers():
                # Filter out resource fork information for automatic production of mac
                if Path(member.name).name.startswith("._"):
                    continue
                if member.issym() or member.islnk():
                    msg = f"Refusing to extract link member from TAR File: {member.name!r} -> {member.linkname!r}"
                    raise ValueError(msg)
                if not (member.isfile() or member.isdir()):
                    msg = f"Refusing to extract non-regular TAR member: {member.name!r}"
                    raise ValueError(msg)
                member_path = output_dir / member.name
                # Ensure no path traversal outside `output_dir`
                if not member_path.resolve().is_relative_to(output_dir.resolve()):
                    msg = f"Attempted Path Traversal in TAR File: {member.name}"
                    raise ValueError(msg)
                bundle.extract(member, path=output_dir)

        # Check and extract based on file type
        if is_zipfile(bundle_path):
            with ZipFile(bundle_path, "r") as zip_bundle:
                _safe_extract_zip(zip_bundle, output_dir)
        elif tarfile.is_tarfile(bundle_path):
            with tarfile.open(bundle_path, "r:*") as tar_bundle:
                _safe_extract_tar(tar_bundle, output_dir)
        else:
            msg = f"Unsupported bundle format: {bundle_path.suffix}"
            raise ValueError(msg)

    def _filter_and_mark_files(self, files: list[BaseFile]) -> list[BaseFile]:
        """Validate file types and filter out invalid files.

        Args:
            files (list[BaseFile]): List of BaseFile instances.

        Returns:
            list[BaseFile]: Validated BaseFile instances.

        Raises:
            ValueError: If unsupported files are encountered and `ignore_unsupported_extensions` is False.
        """
        settings = get_settings_service().settings
        is_s3_storage = settings.storage_type == "s3"
        final_files = []
        ignored_files = []

        for file in files:
            # For local storage, verify the path is actually a file
            # For S3 storage, paths are virtual keys that don't exist locally
            if not is_s3_storage and not file.path.is_file():
                self.log(f"Not a file: {file.path.name}")
                continue

            # Validate file extension
            extension = file.path.suffix[1:].lower() if file.path.suffix else ""
            if extension not in self.valid_extensions:
                # For local storage, optionally ignore unsupported extensions
                if not is_s3_storage and self.ignore_unsupported_extensions:
                    ignored_files.append(file.path.name)
                    continue

                msg = f"Unsupported file extension: {file.path.suffix}"
                self.log(msg)
                if not self.silent_errors:
                    raise ValueError(msg)

            final_files.append(file)

        if ignored_files:
            self.log(f"Ignored files: {ignored_files}")

        return final_files
