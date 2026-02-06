"""Base module for vertex-related functionality."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

import pandas as pd

from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.services.deps import get_storage_service
from lfx.utils.constants import DIRECT_TYPES
from lfx.utils.util import unescape_string

if TYPE_CHECKING:
    from lfx.graph.edge.base import CycleEdge
    from lfx.graph.vertex.base import Vertex


class ParameterHandler:
    """Handles parameter processing for vertices."""

    def __init__(self, vertex: Vertex, storage_service) -> None:
        """Initialize the parameter handler.

        Args:
            vertex: The vertex to handle parameters for.
            storage_service: The storage service to use.
        """
        self.vertex = vertex
        self.template_dict: dict[str, dict] = {
            key: value for key, value in vertex.data["node"]["template"].items() if isinstance(value, dict)
        }
        self.params: dict[str, Any] = {}
        self.load_from_db_fields: list[str] = []
        # Lazy initialization of storage service
        self._storage_service = storage_service
        self._storage_service_initialized = False

    @property
    def storage_service(self):
        """Lazily initialize storage service only when accessed."""
        if not self._storage_service_initialized:
            if self._storage_service is None:
                self._storage_service = get_storage_service()
            self._storage_service_initialized = True
        return self._storage_service

    def process_edge_parameters(self, edges: list[CycleEdge]) -> dict[str, Any]:
        """Process parameters from edges.

        Some params are required, some are optional, and some params are Python base classes
        (like str) while others are LangChain objects (like LLMChain, BasePromptTemplate).
        This method distinguishes between them and sets the appropriate parameters.

        Args:
            edges: A list of edges connected to the vertex.

        Returns:
            A dictionary of processed parameters.
        """
        params: dict[str, Any] = {}
        for edge in edges:
            if not hasattr(edge, "target_param"):
                continue
            params = self._set_params_from_normal_edge(params, edge)
        return params

    def _set_params_from_normal_edge(self, params: dict[str, Any], edge: CycleEdge) -> dict[str, Any]:
        param_key = edge.target_param

        if param_key in self.template_dict and edge.target_id == self.vertex.id:
            field = self.template_dict[param_key]
            if field.get("list"):
                if param_key not in params:
                    params[param_key] = []
                params[param_key].append(self.vertex.graph.get_vertex(edge.source_id))
            else:
                params[param_key] = self.process_non_list_edge_param(field, edge)
        elif param_key in self.vertex.output_names:
            # If the param_key is in the output_names, it means that the loop is run
            #  if the loop is run the param_key item will be set over here
            # validate the edge
            params[param_key] = self.vertex.graph.get_vertex(edge.source_id)
        return params

    def process_non_list_edge_param(self, field: dict, edge: CycleEdge) -> Any:
        """Process non-list edge parameters."""
        param_dict = field.get("value")
        if isinstance(param_dict, dict) and len(param_dict) == 1:
            return {key: self.vertex.graph.get_vertex(edge.source_id) for key in param_dict}
        return self.vertex.graph.get_vertex(edge.source_id)

    def process_field_parameters(self) -> tuple[dict[str, Any], list[str]]:
        """Process parameters from template fields.

        For each key in the template dictionary:
            - If the field type is 'file', process file-related parameters.
            - If the field type is in DIRECT_TYPES, handle direct type parameters.
            - Handle optional fields by setting default values or removing them.

        Returns:
            A tuple containing:
                - A dictionary of processed field parameters.
                - A list of fields that need to be loaded from the database.
        """
        params: dict[str, Any] = {}
        load_from_db_fields: list[str] = []

        for field_name, field in self.template_dict.items():
            if self.should_skip_field(field_name, field, params):
                continue

            if field.get("type") == "file":
                params = self.process_file_field(field_name, field, params)
            elif field.get("type") in DIRECT_TYPES and params.get(field_name) is None:
                params, load_from_db_fields = self._process_direct_type_field(
                    field_name, field, params, load_from_db_fields
                )
            else:
                msg = f"Field {field_name} in {self.vertex.display_name} is not a valid field type: {field.get('type')}"
                raise ValueError(msg)

            self.handle_optional_field(field_name, field, params)

        return params, load_from_db_fields

    def should_skip_field(self, field_name: str, field: dict, params: dict[str, Any]) -> bool:
        """Determine if field should be skipped."""
        if field.get("override_skip"):
            return False
        return (
            field.get("type") == "other"
            or field_name in params
            or field_name == "_type"
            or (not field.get("show") and field_name != "code")
        )

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename to prevent path traversal attacks.

        Args:
            filename: The filename to sanitize.

        Returns:
            A safe filename with only the base name component.
        """
        from pathlib import Path
        from urllib.parse import unquote

        # Decode any percent-encoded characters
        decoded = unquote(filename)
        # Extract only the base filename, stripping any directory components
        return Path(decoded).name

    def _is_path_within_directory(self, path: str, directory: str) -> bool:
        """Check if a resolved path is within the allowed directory.

        Args:
            path: The path to check.
            directory: The directory that should contain the path.

        Returns:
            True if the path is within the directory, False otherwise.
        """
        from pathlib import Path

        try:
            resolved_path = Path(path).resolve()
            resolved_dir = Path(directory).resolve()
            return resolved_path.is_relative_to(resolved_dir)
        except (ValueError, OSError):
            return False

    def _resolve_file_with_fallback(self, logical_path: str) -> str:
        """Resolve a file path with fallback to files directory or project directory.

        First tries the storage service resolution. If the file doesn't exist,
        falls back to looking for the file by name in:
        1. files_dir (if specified via --files-dir CLI option)
        2. project_path (the directory containing the flow JSON)

        This is useful for lfx standalone mode where files are stored locally.

        Args:
            logical_path: Path in format "flow_id/filename" or absolute path

        Returns:
            str: Resolved path to an existing file, or the original resolved path
        """
        from pathlib import Path

        # Extract and sanitize filename from logical path (format: "flow_id/filename")
        raw_filename = logical_path.split("/")[-1] if "/" in logical_path else logical_path
        filename = self._sanitize_filename(raw_filename)

        # Try storage service resolution first
        if self.storage_service is not None:
            resolved_path = self.storage_service.resolve_component_path(logical_path)
        else:
            resolved_path = logical_path

        # Check if the resolved file exists
        if Path(resolved_path).exists():
            return resolved_path

        # File not found - try fallback directories
        fallback_dirs = []
        if hasattr(self.vertex, "graph") and self.vertex.graph is not None:
            # Priority 1: files_dir (explicit --files-dir option)
            files_dir = self.vertex.graph.context.get("files_dir")
            if files_dir:
                fallback_dirs.append(files_dir)

            # Priority 2: project_path (flow JSON directory)
            project_path = self.vertex.graph.context.get("project_path")
            if project_path and project_path != files_dir:
                fallback_dirs.append(project_path)

        for fallback_dir in fallback_dirs:
            # Try to find file by sanitized name in fallback directory
            fallback_path = Path(fallback_dir) / filename
            resolved_fallback = str(fallback_path.resolve())

            # Validate path containment to prevent path traversal
            if not self._is_path_within_directory(resolved_fallback, fallback_dir):
                logger.warning(
                    f"Path traversal attempt detected for '{raw_filename}', "
                    f"skipping fallback directory '{fallback_dir}'"
                )
                continue

            if fallback_path.exists():
                logger.info(f"File '{filename}' not found at '{resolved_path}', using fallback: '{fallback_path}'")
                return resolved_fallback

            # Also try just the base filename (in case logical path has subdirectories)
            base_filename = Path(filename).name
            if base_filename != filename:
                fallback_path = Path(fallback_dir) / base_filename
                resolved_fallback = str(fallback_path.resolve())

                # Validate path containment
                if not self._is_path_within_directory(resolved_fallback, fallback_dir):
                    logger.warning(
                        f"Path traversal attempt detected for '{base_filename}', "
                        f"skipping fallback directory '{fallback_dir}'"
                    )
                    continue

                if fallback_path.exists():
                    logger.info(f"File '{filename}' not found at '{resolved_path}', using fallback: '{fallback_path}'")
                    return resolved_fallback

        # No fallback found - return original resolved path (will fail later with clear error)
        return resolved_path

    def process_file_field(self, field_name: str, field: dict, params: dict[str, Any]) -> dict[str, Any]:
        """Process file type fields.

        Converts logical paths (flow_id/filename) to component-ready paths.
        Falls back to project directory if file not found in storage.
        """
        if file_path := field.get("file_path"):
            try:
                full_path: str | list[str] = ""
                if field.get("list"):
                    full_path = []
                    if isinstance(file_path, str):
                        file_path = [file_path]
                    for p in file_path:
                        resolved = self._resolve_file_with_fallback(p)
                        full_path.append(resolved)
                else:
                    full_path = self._resolve_file_with_fallback(file_path)

            except ValueError as e:
                if "too many values to unpack" in str(e):
                    full_path = file_path
                else:
                    raise
            params[field_name] = full_path
        elif field.get("required"):
            field_display_name = field.get("display_name")
            logger.warning(
                "File path not found for %s in component %s. Setting to None.",
                field_display_name,
                self.vertex.display_name,
            )
            params[field_name] = None
        elif field["list"]:
            params[field_name] = []
        else:
            params[field_name] = None
        return params

    def _process_direct_type_field(
        self, field_name: str, field: dict, params: dict[str, Any], load_from_db_fields: list[str]
    ) -> tuple[dict[str, Any], list[str]]:
        """Process direct type fields."""
        val = field.get("value")

        if field.get("type") == "code":
            params = self._handle_code_field(field_name, val, params)
        elif field.get("type") in {"dict", "NestedDict"}:
            params = self._handle_dict_field(field_name, val, params)
        elif field.get("type") == "table":
            params = self._handle_table_field(field_name, val, params, load_from_db_fields)
        else:
            params = self._handle_other_direct_types(field_name, field, val, params)

        if field.get("load_from_db"):
            load_from_db_fields.append(field_name)

        return params, load_from_db_fields

    def _handle_table_field(
        self,
        field_name: str,
        val: Any,
        params: dict[str, Any],
        load_from_db_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Handle table field type with load_from_db column support."""
        if load_from_db_fields is None:
            load_from_db_fields = []
        if val is None:
            params[field_name] = []
            return params

        # Store the table data as-is for now
        # The actual column processing will happen in the loading phase
        if isinstance(val, list) and all(isinstance(item, dict) for item in val):
            params[field_name] = val
        else:
            msg = f"Invalid value type {type(val)} for table field {field_name}"
            raise ValueError(msg)

        # Get table schema from the field to identify load_from_db columns
        field_template = self.template_dict.get(field_name, {})
        table_schema = field_template.get("table_schema", [])

        # Track which columns need database loading
        load_from_db_columns = []
        for column_schema in table_schema:
            if isinstance(column_schema, dict) and column_schema.get("load_from_db"):
                load_from_db_columns.append(column_schema["name"])
            elif hasattr(column_schema, "load_from_db") and column_schema.load_from_db:
                load_from_db_columns.append(column_schema.name)

        # Store metadata for later processing
        if load_from_db_columns:
            # Store table column metadata for the loading phase
            table_load_metadata_key = f"{field_name}_load_from_db_columns"
            params[table_load_metadata_key] = load_from_db_columns

            # Add to load_from_db_fields so it gets processed
            # We'll use a special naming convention to identify table fields
            load_from_db_fields.append(f"table:{field_name}")
            self.load_from_db_fields.append(f"table:{field_name}")

        return params

    def handle_optional_field(self, field_name: str, field: dict, params: dict[str, Any]) -> None:
        """Handle optional fields."""
        if not field.get("required") and params.get(field_name) is None:
            if field.get("default"):
                params[field_name] = field.get("default")
            else:
                params.pop(field_name, None)

    def _handle_code_field(self, field_name: str, val: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle code field type."""
        try:
            if field_name == "code":
                params[field_name] = val
            else:
                params[field_name] = ast.literal_eval(val) if val else None
        except Exception:  # noqa: BLE001
            logger.debug("Error evaluating code for %s", field_name)
            params[field_name] = val
        return params

    def _handle_dict_field(self, field_name: str, val: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle dictionary field type."""
        match val:
            case list():
                params[field_name] = {k: v for item in val for k, v in item.items()}
            case dict():
                params[field_name] = val
        return params

    def _handle_other_direct_types(
        self, field_name: str, field: dict, val: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle other direct type fields."""
        if val is None:
            return params

        match field.get("type"):
            case "int":
                try:
                    params[field_name] = int(val)
                except ValueError:
                    params[field_name] = val
            case "float" | "slider":
                try:
                    params[field_name] = float(val)
                except ValueError:
                    params[field_name] = val
            case "str":
                match val:
                    case list():
                        params[field_name] = [unescape_string(v) for v in val]
                    case str():
                        params[field_name] = unescape_string(val)
                    case Data():
                        params[field_name] = unescape_string(val.get_text())
            case "bool":
                match val:
                    case bool():
                        params[field_name] = val
                    case str():
                        params[field_name] = bool(val)
            case "table" | "tools":
                if isinstance(val, list) and all(isinstance(item, dict) for item in val):
                    params[field_name] = pd.DataFrame(val)
                else:
                    msg = f"Invalid value type {type(val)} for field {field_name}"
                    raise ValueError(msg)
            case _:
                if val:
                    params[field_name] = val

        return params
