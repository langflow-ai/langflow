"""Validate one fixed CompanyEnrich operation before any network activity."""

import math
from typing import Any, NoReturn
from urllib.parse import quote
from uuid import UUID

from lfx_bundles.companyenrich._catalog import OPERATIONS, SCHEMAS

INT64_MAX = 9223372036854775807
MAX_PAGE_SIZE = 100
MAX_RESULTS = 10000


def _resolve(schema: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        schema = SCHEMAS[schema["$ref"]]
    return schema


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _value(value: Any, schema: dict[str, Any], name: str) -> Any:
    schema = _resolve(schema)
    if isinstance(value, dict) and any(not isinstance(key, str) for key in value):
        _fail(f"{name} must have string keys")
    if value is None:
        if not schema or schema.get("nullable") or None in schema.get("enum", []):
            return None
        _fail(f"{name} cannot be null")
    kind = schema.get("type")
    if schema.get("format") == "int64" and isinstance(value, str):
        if not value.isascii() or not value.isdecimal():
            _fail(f"{name} must be a positive int64 or decimal string")
        value = int(value)
    if kind in {"integer", "number"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _fail(f"{name} must be a number, not a boolean")
        if (isinstance(value, float) and not math.isfinite(value)) or (kind == "integer" and type(value) is not int):
            _fail(f"{name} must be a finite {kind}")
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            _fail(f"{name} is outside its documented range")
        if schema.get("format") == "int64" and not 1 <= value <= INT64_MAX:
            _fail(f"{name} must be a positive int64")
    elif kind == "boolean":
        if type(value) is not bool:
            _fail(f"{name} must be a boolean")
    elif kind == "string":
        if not isinstance(value, str):
            _fail(f"{name} must be a string")
        if len(value) > schema.get("maxLength", math.inf):
            _fail(f"{name} exceeds its documented maximum length")
        if name.rsplit(".", 1)[-1] in {"domain", "email", "id", "jobId"} or "domains[" in name:
            if not value.strip():
                _fail(f"{name} must not be empty")
            value = value.strip()
        if schema.get("format") == "uuid":
            try:
                UUID(value)
            except (ValueError, TypeError, AttributeError):
                _fail(f"{name} must be a UUID")
    elif kind == "array":
        if not isinstance(value, list):
            _fail(f"{name} must be an array")
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", math.inf):
            _fail(f"{name} has an invalid number of items")
        value = [_value(item, schema.get("items", {}), f"{name}[{index}]") for index, item in enumerate(value)]
    elif kind == "object":
        if not isinstance(value, dict):
            _fail(f"{name} must be an object")
        properties = _resolve(schema.get("properties", {}))
        for required in schema.get("required", []):
            if required not in value or value[required] is None:
                _fail(f"{name}.{required} is required")
        value = {key: _value(item, properties.get(key, {}), f"{name}.{key}") for key, item in value.items()}
    if "enum" in schema and value not in schema["enum"]:
        _fail(f"{name} must be one of the documented values")
    # Unknown evolving filter fields are retained, but must remain valid JSON.
    if isinstance(value, float) and not math.isfinite(value):
        _fail(f"{name} must be finite")
    if not schema:
        if isinstance(value, dict):
            return {key: _value(item, {}, f"{name}.{key}") for key, item in value.items()}
        if isinstance(value, list):
            return [_value(item, {}, f"{name}[]") for item in value]
        if not isinstance(value, (str, int, float, bool, type(None))):
            _fail(f"{name} must contain JSON values")
    return value


def _pagination(value: dict[str, Any], *, ceiling: bool = False) -> None:
    for key in ("page", "pageSize"):
        if key in value and (type(value[key]) is not int or value[key] < 1):
            _fail(f"{key} must be a positive integer")
    if value.get("pageSize", 1) > MAX_PAGE_SIZE:
        _fail("pageSize must not exceed 100")
    if ceiling and value.get("page", 1) * value.get("pageSize", 1) > MAX_RESULTS:
        _fail("page * pageSize must not exceed 10000")


def prepare_request(
    operation: str,
    *,
    body: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    path_parameters: dict[str, Any] | None = None,
    allow_beta: bool = False,
) -> tuple[str, str, dict[str, Any], dict[str, Any] | None]:
    """Validate and map one catalog operation; never accept an arbitrary URL."""
    if not isinstance(operation, str) or operation not in OPERATIONS:
        _fail("Choose a documented CompanyEnrich operation")
    if type(allow_beta) is not bool:
        _fail("allow_beta must be a boolean")
    op = OPERATIONS[operation]
    if op["beta"] and not allow_beta:
        _fail("This email operation is beta; explicitly set allow_beta=True")
    for name, value in (("body", body), ("query", query), ("path_parameters", path_parameters)):
        if value is not None and not isinstance(value, dict):
            _fail(f"{name} must be an object")
    query = dict(query or {})
    path_parameters = dict(path_parameters or {})
    path = op["path"]
    for location, values in (("query", query), ("path", path_parameters)):
        definitions = {p["name"]: p for p in op["parameters"] if p["in"] == location}
        if set(values) - set(definitions):
            _fail(f"Unknown {location} parameter")
        for name, parameter in definitions.items():
            if parameter["required"] and (
                name not in values
                or values[name] is None
                or (isinstance(values[name], str) and not values[name].strip())
            ):
                _fail(f"{name} is required")
            if name in values:
                values[name] = _value(values[name], parameter["schema"], name)
                if location == "path":
                    if not str(values[name]).strip() or values[name] in {".", ".."}:
                        _fail("Path parameters must not be empty or traversal segments")
                    path = path.replace("{" + name + "}", quote(str(values[name]), safe=""))
    schema = _resolve(op["body"])
    if not schema and body:
        _fail("This operation does not accept a request body")
    payload: Any = _value(body if body is not None else {}, schema, "body") if schema else None
    _pagination(query)
    if operation in {"post_companies_search", "post_people_search", "post_companies_similar"}:
        payload.setdefault("page", 1)
        payload.setdefault("pageSize", 10)
    if operation in {"post_companies_search_scroll", "post_companies_similar_scroll", "post_people_search_scroll"}:
        payload.setdefault("pageSize", 10)
    if isinstance(payload, dict):
        _pagination(
            payload, ceiling=operation in {"post_companies_search", "post_people_search", "post_companies_similar"}
        )
    if operation == "get_companies_workforce" and sum(bool(query.get(k)) for k in ("id", "domain")) != 1:
        _fail("Provide exactly one company id or domain")
    if operation == "post_companies_enrich":
        properties = _resolve(schema.get("properties", {}))
        if not any(isinstance(payload.get(k), str) and payload[k].strip() for k in properties):
            _fail("Provide at least one documented company matching property")
    if operation.startswith("post_companies_similar"):
        if operation != "post_companies_similar" and "domain" in payload:
            _fail("Use domains for this similar-company operation")
        if not payload.get("domains") and not (operation == "post_companies_similar" and payload.get("domain")):
            _fail("Provide one to ten seed domains")
    if operation == "post_companies_search_async" and payload.get("similar") is not None:
        similar = payload["similar"]
        if not similar.get("domains"):
            _fail("Export similar requires one to ten seed domains")
    query = {key: (str(value).lower() if type(value) is bool else value) for key, value in query.items()}
    return op["method"], path, query, payload


def merge_filters(filters: dict[str, Any] | None, **dedicated: Any) -> dict[str, Any]:
    """Preserve filter fields; explicit dedicated values take precedence."""
    if filters is not None and not isinstance(filters, dict):
        _fail("filters must be an object")
    return {**(filters or {}), **{key: value for key, value in dedicated.items() if value is not None}}
