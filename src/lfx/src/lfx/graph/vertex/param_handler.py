"""Base module for vertex-related functionality."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any

import pandas as pd

from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.services.deps import get_storage_service
from lfx.utils.constants import DIRECT_TYPES
from lfx.utils.file_path_security import (
    LocalFileAccessError,
    StorageNamespaceError,
    enforce_local_file_access,
    enforce_storage_key_scope,
    is_local_file_access_restricted,
)
from lfx.utils.util import unescape_string

if TYPE_CHECKING:
    from lfx.graph.edge.base import CycleEdge
    from lfx.graph.vertex.base import Vertex


def _coerce_str_value(v: Any) -> str:
    """Coerce a value to string for str-typed fields, handling Message/Data/dict objects."""
    if isinstance(v, str):
        return unescape_string(v)
    if isinstance(v, Data):
        return unescape_string(v.get_text())
    if isinstance(v, dict):
        # Serialized Message or Data -- extract text from nested structure
        data = v.get("data")
        nested_text = data.get("text", "") if isinstance(data, dict) else ""
        text = v.get("text", nested_text)
        return unescape_string(text) if isinstance(text, str) else str(v)
    return str(v)


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
        self._canonical_file_fields_cache: dict[str, dict[str, Any]] | None = None

    @property
    def storage_service(self):
        """Lazily initialize storage service only when accessed."""
        if not self._storage_service_initialized:
            if self._storage_service is None:
                self._storage_service = get_storage_service()
            self._storage_service_initialized = True
        return self._storage_service

    @staticmethod
    def _file_input_names_from_code(code: str) -> set[str]:
        """Extract literal FileInput names from trusted component source."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return set()

        aliases = {"FileInput"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                aliases.update(alias.asname or alias.name for alias in node.names if alias.name == "FileInput")

        names: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            is_file_input = (isinstance(node.func, ast.Name) and node.func.id in aliases) or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "FileInput"
            )
            if not is_file_input:
                continue
            for keyword in node.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str) and keyword.value.value:
                        names.add(keyword.value.value)
                    break
        return names

    def _canonical_file_fields(self) -> dict[str, dict[str, Any]]:
        """Return FileInput metadata derived from server-trusted component source."""
        if self._canonical_file_fields_cache is not None:
            return self._canonical_file_fields_cache

        canonical_fields: dict[str, dict[str, Any]] = {}
        code_field = self.template_dict.get("code")
        submitted_code = code_field.get("value") if isinstance(code_field, dict) else None
        if not isinstance(submitted_code, str) or not submitted_code:
            self._canonical_file_fields_cache = canonical_fields
            return canonical_fields

        # The flow policy may substitute a server-owned source for a matching
        # submitted hash. Use that same trusted source for input classification;
        # an exact source comparison below prevents request metadata from
        # declaring what is or is not a FileInput.
        from lfx.interface.components import component_cache
        from lfx.utils.flow_validation import get_trusted_code_for_validation

        trusted_code = get_trusted_code_for_validation(submitted_code) or submitted_code
        all_types_dict = component_cache.all_types_dict
        if isinstance(all_types_dict, Mapping):
            for category_components in all_types_dict.values():
                if not isinstance(category_components, Mapping):
                    continue
                for component_data in category_components.values():
                    if not isinstance(component_data, Mapping):
                        continue
                    template = component_data.get("template")
                    if not isinstance(template, Mapping):
                        continue
                    server_code_field = template.get("code")
                    server_code = server_code_field.get("value") if isinstance(server_code_field, Mapping) else None
                    if server_code != trusted_code:
                        continue
                    for field_name, field in template.items():
                        if not isinstance(field_name, str) or not isinstance(field, Mapping):
                            continue
                        if field.get("type") == "file" or field.get("_input_type") == "FileInput":
                            canonical_fields.setdefault(field_name, dict(field))

        # Direct declarations remain detectable while the component registry is
        # warming, and cover older trusted component versions absent from the
        # current registry. Registry metadata above still supplies list/required
        # semantics for inherited or dynamically assembled inputs.
        for field_name in self._file_input_names_from_code(trusted_code):
            canonical_fields.setdefault(
                field_name,
                {"type": "file", "_input_type": "FileInput", "list": False, "required": False},
            )

        self._canonical_file_fields_cache = canonical_fields
        return canonical_fields

    def _effective_file_field(self, field_name: str, field: dict[str, Any]) -> dict[str, Any]:
        """Overlay server-owned FileInput semantics on request-supplied values."""
        canonical = self._canonical_file_fields().get(field_name)
        if canonical is None:
            return field

        effective = dict(field)
        for key in ("type", "_input_type", "list", "required", "display_name"):
            if key in canonical:
                effective[key] = canonical[key]
        effective["type"] = "file"
        effective["_canonical_file_input"] = True
        effective.setdefault("list", False)
        return effective

    @staticmethod
    def _is_file_field(field: Mapping[str, Any]) -> bool:
        return field.get("type") == "file" or field.get("_input_type") == "FileInput"

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

        restricted = is_local_file_access_restricted()
        for field_name, request_field in self.template_dict.items():
            field = self._effective_file_field(field_name, request_field) if restricted else request_field
            if self.should_skip_field(field_name, field, params):
                continue

            if self._is_file_field(field):
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

    def process_file_field(self, field_name: str, field: dict, params: dict[str, Any]) -> dict[str, Any]:
        """Process file type fields.

        Converts logical paths (flow_id/filename) to component-ready paths.
        """
        file_path = field.get("file_path")
        if not file_path and field.get("_canonical_file_input"):
            file_path = field.get("value")
        if file_path:
            params[field_name] = self.process_file_value(file_path, is_list=bool(field.get("list")))
        elif field.get("required"):
            field_display_name = field.get("display_name")
            logger.warning(
                "File path not found for %s in component %s. Setting to None.",
                field_display_name,
                self.vertex.display_name,
            )
            params[field_name] = None
        elif field.get("list"):
            params[field_name] = []
        else:
            params[field_name] = None
        return params

    def process_runtime_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Resolve and contain FileInput values supplied as runtime tweaks."""
        processed = params.copy()
        restricted = is_local_file_access_restricted()

        for field_name, value in processed.items():
            request_field = self.template_dict.get(field_name, {})
            field = self._effective_file_field(field_name, request_field)
            empty_value = value is None or (isinstance(value, str | list) and not value)
            if not self._is_file_field(field) or empty_value:
                continue
            file_value = value
            if isinstance(value, dict):
                if "file_path" in value:
                    file_value = value["file_path"]
                elif set(value) == {"value"}:
                    file_value = value["value"]
                else:
                    msg = "Runtime FileInput tweaks must provide a file path."
                    raise LocalFileAccessError(msg)
            if file_value is None or (isinstance(file_value, str | list) and not file_value):
                continue

            is_list = bool(field.get("list")) or isinstance(file_value, list)
            if restricted:
                processed[field_name] = self.process_file_value(file_value, is_list=is_list)
            else:
                # Unrestricted local paths are a documented single-tenant feature. Inspect
                # their storage-key shape without resolving or rewriting the caller's value.
                self._validate_unrestricted_file_value(file_value, is_list=is_list)
        return processed

    def _validate_unrestricted_file_value(self, file_path: Any, *, is_list: bool) -> None:
        """Validate an unrestricted FileInput value without changing its representation."""
        if is_list:
            paths = [file_path] if isinstance(file_path, str) else file_path
            if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
                msg = "FileInput values must be file path strings."
                raise LocalFileAccessError(msg)
        else:
            if not isinstance(file_path, str):
                msg = "FileInput values must be file path strings."
                raise LocalFileAccessError(msg)
            paths = [file_path]

        for path in paths:
            self._validate_unrestricted_file_path(path)

    def _scoped_storage_key(self, file_path: str) -> str:
        """Reject a logical storage key whose namespace is outside the executing graph.

        ``StorageService.resolve_component_path`` turns a relative ``"<namespace>/<file_name>"``
        value into ``<storage root>/<namespace>/<file_name>``, so the namespace segment selects a
        per-principal storage location. The value comes from the saved template or a runtime
        tweak, so it has to be checked *before* it is resolved — afterwards the component only
        sees an already-resolved path and the shape of the input has decided access on its own.

        These cases are deliberately left alone:

        * Absolute paths are not storage keys. Reading a local server file by absolute path is
          the documented single-tenant behavior that
          ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS`` governs, so they stay with
          ``_enforce_file_paths``. Absoluteness is tested against both flavours: a Windows
          drive-letter path written with forward slashes ("C:/data/report.csv") is not
          POSIX-absolute, so testing only ``PurePosixPath`` would split it into namespace
          "C:" and reject a legitimate local path -- while the backslash spelling of the
          same path must remain legitimate too.
        * Separatorless relative values are local file names, not storage keys.
        * Restricted mode, where ``_enforce_file_paths`` already pins the resolved local path and
          the S3 logical key to the graph's own scopes. This check exists to close the
          unrestricted default, and skipping it keeps restricted behavior byte-identical.
        """
        if is_local_file_access_restricted():
            return file_path
        return self._validate_unrestricted_file_path(file_path)

    def _validate_unrestricted_file_path(self, file_path: str) -> str:
        """Validate a path's storage-key shape without resolving or rewriting it."""
        if PurePosixPath(file_path).is_absolute() or PureWindowsPath(file_path).is_absolute():
            return file_path
        if "\\" in file_path:
            msg = "Relative FileInput paths must not contain backslash separators or traversal sequences."
            raise StorageNamespaceError(msg)
        if "/" not in file_path:
            return file_path
        enforce_storage_key_scope(file_path, self._file_access_scopes())
        return file_path

    def process_file_value(self, file_path: str | list[str], *, is_list: bool) -> str | list[str]:
        """Resolve a FileInput value and enforce the configured storage boundary."""
        try:
            if is_list:
                paths = [file_path] if isinstance(file_path, str) else file_path
                if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
                    msg = "FileInput values must be file path strings."
                    raise LocalFileAccessError(msg)
                full_path: str | list[str] = [
                    self.storage_service.resolve_component_path(self._scoped_storage_key(path)) for path in paths
                ]
            else:
                if not isinstance(file_path, str):
                    msg = "FileInput values must be file path strings."
                    raise LocalFileAccessError(msg)
                full_path = self.storage_service.resolve_component_path(self._scoped_storage_key(file_path))
        except StorageNamespaceError:
            # A namespace denial must never be downgraded. It is a ValueError subclass, so the
            # broad handler below would otherwise decide its fate by substring-matching an
            # unrelated message -- correct today, but one added branch away from silently
            # turning a cross-tenant denial back into a read.
            raise
        except ValueError as e:
            if "too many values to unpack" in str(e):
                full_path = file_path
            else:
                raise
        return self._enforce_file_paths(full_path)

    def _file_access_scopes(self) -> list[str]:
        """Return server-established storage namespaces for the executing graph."""
        graph = getattr(self.vertex, "graph", None)
        scopes: list[str] = []
        for candidate in (
            getattr(graph, "user_id", None),
            getattr(graph, "flow_id", None),
            getattr(graph, "source_flow_id", None),
        ):
            if candidate is not None:
                scope = str(candidate).strip()
                if scope and scope not in scopes:
                    scopes.append(scope)
        return scopes

    def _enforce_file_paths(self, file_paths: str | list[str]) -> str | list[str]:
        """Apply storage-specific containment before FileInput values reach components."""
        storage_settings = getattr(getattr(self.storage_service, "settings_service", None), "settings", None)
        storage_type = str(getattr(storage_settings, "storage_type", "local")).lower()
        if not is_local_file_access_restricted():
            return file_paths

        scopes = self._file_access_scopes()
        if storage_type == "s3":
            if isinstance(file_paths, list):
                return [self._enforce_s3_logical_key(path, scopes) for path in file_paths]
            return self._enforce_s3_logical_key(file_paths, scopes)

        if isinstance(file_paths, list):
            return [str(enforce_local_file_access(path, scope_ids=scopes)) for path in file_paths]
        return str(enforce_local_file_access(file_paths, scope_ids=scopes))

    @staticmethod
    def _enforce_s3_logical_key(file_path: str, scopes: list[str]) -> str:
        """Reject S3 logical keys that could be interpreted as foreign local paths."""
        path = str(file_path)
        segments = path.split("/")
        logical_path = PurePosixPath(path)
        if (
            not path
            or "\x00" in path
            or "\\" in path
            or logical_path.is_absolute()
            or any(segment in {"", ".", ".."} for segment in segments)
            or not logical_path.parts
            or logical_path.parts[0] not in scopes
        ):
            msg = "S3 file references must stay within the authenticated user's or executing flow's namespace."
            raise LocalFileAccessError(msg)
        return path

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
            # Skip load_from_db if the field itself has an incoming edge
            has_incoming_edge = self.vertex.get_incoming_edge_by_target_param(field_name) is not None
            # Skip credential fields when the model field has an incoming edge,
            # because the connected model component provides its own credentials
            is_secret = field.get("_input_type") == "SecretStrInput" or field.get("password")
            model_has_edge = (
                is_secret
                and "model" in self.template_dict
                and self.vertex.get_incoming_edge_by_target_param("model") is not None
            )
            # Skip credential fields when the node is in "Connect other models" mode
            # (user chose to wire an external model instead of the built-in provider)
            model_field = self.template_dict.get("model", {})
            in_connection_mode = is_secret and model_field.get("_connection_mode", False)
            if not has_incoming_edge and not model_has_edge and not in_connection_mode:
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
                # Convert list of {"key": k, "value": v} pairs to a flat dict.
                # e.g. [{"key": "h1", "value": "v1"}, {"key": "h2", "value": "v2"}] -> {"h1": "v1", "h2": "v2"}
                if val and all(isinstance(item, dict) and "key" in item and "value" in item for item in val):
                    params[field_name] = {item["key"]: item["value"] for item in val}
                else:
                    # Merge generic list of dicts into a single dict.
                    # e.g. [{"a": 1}, {"b": 2}] -> {"a": 1, "b": 2}
                    params[field_name] = {k: v for item in val for k, v in item.items()}
            case dict():
                params[field_name] = val
            case _:
                logger.warning(
                    "Unexpected type %s for dict field '%s'; expected list or dict, got %r",
                    type(val).__name__,
                    field_name,
                    val,
                )
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
                        params[field_name] = [_coerce_str_value(v) for v in val]
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
