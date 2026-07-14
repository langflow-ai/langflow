"""Fail-closed sanitization for workflow snapshots published as team templates."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

SANITIZER_VERSION = 1

_SENSITIVE_KEY = re.compile(
    r"(^|[_-])(api[_-]?key|password|passwd|secret|token|access[_-]?key|private[_-]?key|credential)s?($|[_-])",
    re.IGNORECASE,
)
_SENSITIVE_LITERAL = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bBearer\s+[A-Za-z0-9._-]{20,}|\bsk-[A-Za-z0-9_-]{20,})"
)
_SENSITIVE_CONTAINER_KEYS = {"auth", "credentials", "environment", "env", "headers", "secrets"}
_FILE_REFERENCE_KEYS = {
    "file_id",
    "file_ids",
    "file_path",
    "file_paths",
    "fs_path",
    "local_path",
    "path",
    "save_path",
    "temp_path",
}
_STRUCTURAL_HIDDEN_FIELDS = {"code"}


@dataclass
class SanitizationReport:
    cleared_paths: list[str] = field(default_factory=list)

    @property
    def cleared_count(self) -> int:
        return len(self.cleared_paths)

    def record(self, path: str) -> None:
        if path not in self.cleared_paths:
            self.cleared_paths.append(path)


def _empty_like(value: Any) -> Any:
    if isinstance(value, list):
        return []
    if isinstance(value, dict):
        return {}
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return None
    return ""


def _clear(mapping: dict[str, Any], key: str, path: str, report: SanitizationReport) -> None:
    if key not in mapping:
        return
    mapping[key] = _empty_like(mapping[key])
    report.record(path)


def _sanitize_table_variables(field_value: Any, table_schema: Any, path: str, report: SanitizationReport) -> None:
    if not isinstance(field_value, list) or not isinstance(table_schema, list):
        return
    variable_columns = {
        column.get("name")
        for column in table_schema
        if isinstance(column, dict) and column.get("load_from_db") is True and column.get("name")
    }
    if not variable_columns:
        return
    for row_index, row in enumerate(field_value):
        if not isinstance(row, dict):
            continue
        for column_name in variable_columns:
            if column_name in row:
                _clear(row, column_name, f"{path}.value[{row_index}].{column_name}", report)
    for column_index, column in enumerate(table_schema):
        if isinstance(column, dict) and column.get("name") in variable_columns:
            column["load_from_db"] = False
            report.record(f"{path}.table_schema[{column_index}].load_from_db")


def _is_template_field(value: dict[str, Any]) -> bool:
    marker_keys = {"_input_type", "advanced", "hidden", "load_from_db", "password", "show", "type"}
    return "value" in value and bool(marker_keys.intersection(value))


def _walk(value: Any, path: str, report: SanitizationReport) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk(item, f"{path}[{index}]", report)
        return
    if not isinstance(value, dict):
        return

    if _is_template_field(value):
        field_name = path.rsplit(".", 1)[-1]
        is_secret = value.get("password") is True or value.get("_input_type") in {
            "SecretStrInput",
            "SecretStringInput",
        }
        is_variable = value.get("load_from_db") is True
        is_hidden = (value.get("show") is False or value.get("hidden") is True) and field_name not in (
            _STRUCTURAL_HIDDEN_FIELDS
        )
        is_sensitive_name = (
            bool(_SENSITIVE_KEY.search(field_name))
            or field_name.lower() in _SENSITIVE_CONTAINER_KEYS
            or field_name.lower() in _FILE_REFERENCE_KEYS
        )
        _sanitize_table_variables(value.get("value"), value.get("table_schema"), path, report)
        if is_secret or is_variable or is_hidden or is_sensitive_name:
            _clear(value, "value", f"{path}.value", report)
            if "load_from_db" in value:
                value["load_from_db"] = False

    for key in list(value):
        child_path = f"{path}.{key}" if path else key
        lowered = key.lower()
        child = value[key]
        if isinstance(child, dict) and _is_template_field(child):
            _walk(child, child_path, report)
            continue
        if _is_template_field(value) and lowered in {
            "_input_type",
            "hidden",
            "load_from_db",
            "password",
            "show",
            "table_schema",
            "type",
        }:
            _walk(child, child_path, report)
            continue
        if isinstance(child, str) and _SENSITIVE_LITERAL.search(child):
            _clear(value, key, child_path, report)
            continue
        if lowered in _FILE_REFERENCE_KEYS or lowered in _SENSITIVE_CONTAINER_KEYS or _SENSITIVE_KEY.search(lowered):
            # Template field dictionaries are handled above so their metadata survives.
            if not (_is_template_field(value) and key == "value"):
                _clear(value, key, child_path, report)
            continue
        _walk(value[key], child_path, report)


def sanitize_flow_data(flow_data: dict[str, Any]) -> tuple[dict[str, Any], SanitizationReport]:
    """Return a detached, recursively sanitized template snapshot and report."""
    if not isinstance(flow_data, dict) or not isinstance(flow_data.get("nodes"), list):
        msg = "Flow data must contain a nodes list"
        raise TypeError(msg)
    if not isinstance(flow_data.get("edges"), list):
        msg = "Flow data must contain an edges list"
        raise TypeError(msg)

    sanitized = copy.deepcopy(flow_data)
    report = SanitizationReport()
    _walk(sanitized, "data", report)
    return sanitized, report
