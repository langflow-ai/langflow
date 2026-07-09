import asyncio
import contextlib
import inspect
import json
import os
import re
import shlex
import shutil
import unicodedata
from collections.abc import AsyncIterator, Awaitable, Callable
from types import UnionType
from typing import Any, TypedDict, Union, get_args, get_origin
from urllib.parse import urlparse
from uuid import UUID

import httpx
from anyio import ClosedResourceError
from httpx import codes as httpx_codes
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.shared.exceptions import McpError
from pydantic import BaseModel

from lfx.base.agents.utils import maybe_unflatten_dict
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.json_schema import create_input_schema_from_json_schema
from lfx.services.deps import get_settings_service
from lfx.utils.async_helpers import run_until_complete

HTTP_ERROR_STATUS_CODE = httpx_codes.BAD_REQUEST  # HTTP status code for client errors

# HTTP status codes used in validation
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_NOT_ACCEPTABLE = 406
HTTP_BAD_REQUEST = 400
HTTP_TOO_MANY_REQUESTS = 429
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403

# SECURITY: Environment variables that enable code injection via approved MCP
# stdio commands. All comparisons are case-insensitive (see is_dangerous_mcp_env_var).
#
# The stdio launcher runs servers with shell=False (no bash -c / cmd /c wrapper;
# see MCPStdioClient._connect_to_server), which structurally neutralizes the
# shell-startup vectors below. They are retained as defense-in-depth: a fail-safe
# if a shell wrapper is ever reintroduced, and to keep write-time validation
# (MCPServerConfig) aligned with the launch-time backstop. The loader and
# interpreter entries remain load-bearing regardless of the shell, because the
# dynamic linker / target interpreter honors them directly.
DANGEROUS_MCP_ENV_VARS = frozenset(
    {
        # -- Loader / interpreter injection (dangerous even with shell=False) --
        # Shared-object / dylib injection (arbitrary native code in any process)
        "ld_preload",
        "ld_library_path",
        "ld_audit",
        "dyld_insert_libraries",
        "dyld_library_path",
        # glibc iconv module injection (loads arbitrary .so via iconv)
        "gconv_path",
        # Command resolution override (redirects which binary is exec'd)
        "path",
        # Node.js code injection (honored by the node runtime itself)
        "node_options",
        "node_extra_ca_certs",
        # Python code injection (honored by the python runtime itself)
        "pythonstartup",
        "pythonpath",
        # Home / config directory redirection (loads attacker-controlled configs)
        "home",
        "xdg_config_home",
        "xdg_data_home",
        # Temp directory redirection
        "tmpdir",
        "tmp",
        "temp",
        # DNS / network manipulation
        "hostaliases",
        "localdomain",
        "res_options",
        # Locale / getconf injection (can load arbitrary .so on some glibc)
        "getconf_dir",
        # -- Shell-startup vectors (defense-in-depth; inert while shell=False) --
        # Shell startup, option, and tracing injection
        "bash_env",
        "env",
        "bash_func_",
        "shellopts",
        "bashopts",
        "ps4",
        # Shell word-splitting / globbing manipulation
        "ifs",
        "cdpath",
    }
)

# MCP Session Manager constants - lazy loaded
_mcp_settings_cache: dict[str, Any] = {}


def is_dangerous_mcp_env_var(key: str) -> bool:
    lower_key = key.lower()
    return lower_key in DANGEROUS_MCP_ENV_VARS or lower_key.startswith("bash_func_")


def _validate_mcp_stdio_env(env: dict[str, str] | None) -> dict[str, str]:
    if env is None:
        return {}

    for key in env:
        if is_dangerous_mcp_env_var(key):
            msg = f"Environment variable '{key}' is not allowed for MCP stdio servers"
            raise ValueError(msg)

    return env


def _get_mcp_setting(key: str, default: Any = None) -> Any:
    """Lazy load MCP settings from settings service."""
    if key not in _mcp_settings_cache:
        settings = get_settings_service().settings
        _mcp_settings_cache[key] = getattr(settings, key, default)
    return _mcp_settings_cache[key]


def _resolve_mcp_tool_execution_timeout(tool_execution_timeout: float | None) -> float:
    """Resolve MCP tool execution timeout from explicit input or MCP settings.

    Priority for picking the timeout:
    1. `tool_execution_timeout`: Custom UI override directly on the component (Highest).
    2. Global Settings: The maximum value between `mcp_tool_execution_timeout`
       and `mcp_server_timeout` from global settings.
    3. Fallback: 180.0 seconds if no custom or global settings exist (Lowest).

    Negative values are treated as unset (use system default) because
    ``asyncio.wait_for`` immediately raises ``TimeoutError`` for any timeout < 0.
    """
    if tool_execution_timeout is not None and float(tool_execution_timeout) > 0:
        return float(tool_execution_timeout)

    configured = _get_mcp_setting("mcp_tool_execution_timeout", None)
    mcp_server_timeout = _get_mcp_setting("mcp_server_timeout", None)

    configured_timeouts = [float(value) for value in (configured, mcp_server_timeout) if value is not None]
    return max(configured_timeouts) if configured_timeouts else 180.0


def get_max_sessions_per_server() -> int:
    """Get maximum number of sessions per server to prevent resource exhaustion."""
    return _get_mcp_setting("mcp_max_sessions_per_server")


def get_session_idle_timeout() -> int:
    """Get 5 minutes idle timeout for sessions."""
    return _get_mcp_setting("mcp_session_idle_timeout")


def get_session_cleanup_interval() -> int:
    """Get cleanup interval in seconds."""
    return _get_mcp_setting("mcp_session_cleanup_interval")


# RFC 7230 compliant header name pattern: token = 1*tchar
# tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "." /
#         "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA
HEADER_NAME_PATTERN = re.compile(r"^[!#$%&\'*+\-.0-9A-Z^_`a-z|~]+$")

# Common allowed headers for MCP connections
ALLOWED_HEADERS = {
    "authorization",
    "accept",
    "accept-encoding",
    "accept-language",
    "cache-control",
    "content-type",
    "user-agent",
    "x-api-key",
    "x-auth-token",
    "x-custom-header",
    "x-langflow-session",
    "x-mcp-client",
    "x-requested-with",
}


def create_mcp_http_client_with_ssl_option(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
    *,
    verify_ssl: bool = True,
) -> httpx.AsyncClient:
    """Create an httpx AsyncClient with configurable SSL verification.

    This is a custom factory that extends the standard MCP client factory
    to support disabling SSL verification for self-signed certificates.

    Args:
        headers: Optional headers to include with all requests.
        timeout: Request timeout as httpx.Timeout object.
        auth: Optional authentication handler.
        verify_ssl: Whether to verify SSL certificates (default: True).

    Returns:
        Configured httpx.AsyncClient instance.
    """
    kwargs: dict[str, Any] = {
        "follow_redirects": True,
        "verify": verify_ssl,
    }

    if timeout is None:
        kwargs["timeout"] = httpx.Timeout(30.0)
    else:
        kwargs["timeout"] = timeout

    if headers is not None:
        kwargs["headers"] = headers

    if auth is not None:
        kwargs["auth"] = auth

    return httpx.AsyncClient(**kwargs)


def validate_headers(headers: dict[str, str]) -> dict[str, str]:
    """Validate and sanitize HTTP headers according to RFC 7230.

    Args:
        headers: Dictionary of header name-value pairs

    Returns:
        Dictionary of validated and sanitized headers

    Raises:
        ValueError: If headers contain invalid names or values
    """
    if not headers:
        return {}

    sanitized_headers = {}

    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            logger.warning(f"Skipping non-string header: {name}={value}")
            continue

        # Validate header name according to RFC 7230
        if not HEADER_NAME_PATTERN.match(name):
            logger.warning(f"Invalid header name '{name}', skipping")
            continue

        # Normalize header name to lowercase (HTTP headers are case-insensitive)
        normalized_name = name.lower()

        # Optional: Check against whitelist of allowed headers
        if normalized_name not in ALLOWED_HEADERS:
            # For MCP, we'll be permissive and allow non-standard headers
            # but log a warning for security awareness
            logger.debug(f"Using non-standard header: {normalized_name}")

        # Check for potential header injection attempts BEFORE sanitizing
        if "\r" in value or "\n" in value:
            logger.warning(f"Potential header injection detected in '{name}', skipping")
            continue

        # Sanitize header value - remove control characters and newlines
        # RFC 7230: field-value = *( field-content / obs-fold )
        # We'll remove control characters (0x00-0x1F, 0x7F) except tab (0x09) and space (0x20)
        sanitized_value = re.sub(r"[\x00-\x08\x0A-\x1F\x7F]", "", value)

        # Remove leading/trailing whitespace
        sanitized_value = sanitized_value.strip()

        if not sanitized_value:
            logger.warning(f"Header '{name}' has empty value after sanitization, skipping")
            continue

        sanitized_headers[normalized_name] = sanitized_value

    return sanitized_headers


def sanitize_mcp_name(name: str, max_length: int = 46) -> str:
    """Sanitize a name for MCP usage by removing emojis, diacritics, and special characters.

    Args:
        name: The original name to sanitize
        max_length: Maximum length for the sanitized name

    Returns:
        A sanitized name containing only letters, numbers, hyphens, and underscores
    """
    if not name or not name.strip():
        return ""

    # Remove emojis using regex pattern
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "\U00002500-\U00002bef"  # chinese char
        "\U00002702-\U000027b0"
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2b55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+",
        flags=re.UNICODE,
    )

    # Remove emojis
    name = emoji_pattern.sub("", name)

    # Normalize unicode characters to remove diacritics
    name = unicodedata.normalize("NFD", name)
    name = "".join(char for char in name if unicodedata.category(char) != "Mn")

    # Replace spaces and special characters with underscores
    name = re.sub(r"[^\w\s-]", "", name)  # Keep only word chars, spaces, and hyphens
    name = re.sub(r"[-\s]+", "_", name)  # Replace spaces and hyphens with underscores
    name = re.sub(r"_+", "_", name)  # Collapse multiple underscores

    # Remove leading/trailing underscores
    name = name.strip("_")

    # Ensure it starts with a letter or underscore (not a number)
    if name and name[0].isdigit():
        name = f"_{name}"

    # Convert to lowercase
    name = name.lower()

    # Truncate to max length
    if len(name) > max_length:
        name = name[:max_length].rstrip("_")

    # If empty after sanitization, provide a default
    if not name:
        name = "unnamed"

    return name


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    import re

    # Insert an underscore before any uppercase letter that follows a lowercase letter
    s1 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return s1.lower()


def _convert_camel_case_to_snake_case(provided_args: dict[str, Any], arg_schema: type[BaseModel]) -> dict[str, Any]:
    """Convert camelCase field names to snake_case if the schema expects snake_case fields."""
    schema_fields = set(arg_schema.model_fields.keys())
    converted_args = {}

    for key, value in provided_args.items():
        # If the key already exists in schema, use it as-is
        if key in schema_fields:
            converted_args[key] = value
        else:
            # Try converting camelCase to snake_case
            snake_key = _camel_to_snake(key)
            if snake_key in schema_fields:
                converted_args[snake_key] = value
            else:
                # If neither the original nor converted key exists, keep original
                # The validation will catch this error
                converted_args[key] = value

    return converted_args


def _resolve_expected_type(annotation: Any) -> type | None:
    """Resolve the effective expected type from a Pydantic field annotation.

    Handles Union, UnionType (X | None), list, list[X]. Returns the primary
    type (dict, list, int, float, bool, str) or None if not one we normalize.
    """
    ann = annotation
    origin = get_origin(ann)
    if origin is UnionType or origin is Union:
        args = get_args(ann)
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            ann = non_none[0]
            origin = get_origin(ann)
    if origin is list or ann is list:
        return list
    if origin is dict or ann is dict:
        return dict
    if ann in (int, float, bool, str):
        return ann
    return None


def _annotation_accepts_none(annotation: Any) -> bool:
    """Check if annotation accepts None (e.g. Union[X, None], X | None)."""
    origin = get_origin(annotation)
    if origin is UnionType or origin is Union:
        args = get_args(annotation)
        return type(None) in args
    return False


def _is_pydantic_model_type(annotation: Any) -> bool:
    """Check if annotation refers to a Pydantic BaseModel (possibly in Union with None)."""
    ann = annotation
    origin = get_origin(ann)
    if origin is UnionType or origin is Union:
        args = get_args(ann)
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            ann = non_none[0]
    return isinstance(ann, type) and issubclass(ann, BaseModel)


def _unwrap_langflow_json_value(value: Any) -> Any:
    """Return the payload dict from Langflow JSON/Data values wired into MCP object parameters."""
    if isinstance(value, Data):
        return value.data
    return value


def _try_convert_value(value: Any, expected_type: type, field_name: str, tool_name: str) -> Any:
    """Try to convert value to expected type. Raise ValueError with clear message on failure."""

    def _err(type_desc: str, detail: str) -> ValueError:
        msg = f"Tool '{tool_name}': Parameter '{field_name}' expects {type_desc} {detail}"
        return ValueError(msg)

    expected_type_desc = expected_type.__name__

    if value is None and expected_type in (int, float, bool, dict, list):
        raise _err(expected_type_desc, "but received None.")

    if expected_type in (dict, list):
        value = _unwrap_langflow_json_value(value)

    # return correctly typed value, but handle the
    # special case of bool as this is a subclass of int
    # we'll NOT return but raise an error
    if isinstance(value, expected_type) and not (expected_type is int and isinstance(value, bool)):
        return value

    # return custom classes as is
    if expected_type not in (dict, list, int, float, bool):
        return value

    if expected_type in (dict, list):
        expected_type_desc = "object (dict)" if expected_type is dict else "array (list)"
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as e:
                raise _err(expected_type_desc, f"but received invalid JSON string {value!r}; {e}") from e
            if not isinstance(parsed, expected_type):
                raise _err(expected_type_desc, f"but JSON parsed to {type(parsed).__name__}.")
            return parsed

    elif expected_type is int:
        expected_type_desc = "integer (int)"
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as e:
                raise _err(expected_type_desc, f"but received string: {value!r}; could not convert.") from e

    elif expected_type is float:
        expected_type_desc = "number (float)"
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError as e:
                raise _err(expected_type_desc, f"but received string: {value!r}; could not convert.") from e

    elif expected_type is bool and isinstance(value, str):
        expected_type_desc = "boolean (bool)"
        lower = value.strip().lower()
        if lower in ("true", "1", "yes"):
            return True
        if lower in ("false", "0", "no"):
            return False

    detail = f"but received {type(value).__name__}: {value!r}; could not convert."
    raise _err(expected_type_desc, detail)


def _normalize_arguments_for_mcp(
    arguments: dict[str, Any], arg_schema: type[BaseModel], tool_name: str
) -> dict[str, Any]:
    """Normalize tool arguments for MCP: try-convert when value type != schema expected type.

    Uses schema from MCP server (no guessing). On conversion failure, raises
    ValueError with clear user-facing message.
    """
    result: dict[str, Any] = {}
    schema_field_names = set(arg_schema.model_fields.keys())
    for field_name, model_field in arg_schema.model_fields.items():
        value = arguments.get(field_name)
        if value is None:
            if not (model_field.is_required() or field_name in arguments):
                continue
            expected = _resolve_expected_type(model_field.annotation)
            if expected in (list, dict, str) and model_field.is_required():
                result[field_name] = [] if expected is list else ({} if expected is dict else "")
            elif expected in (list, dict, str) and _annotation_accepts_none(model_field.annotation):
                result[field_name] = None
            else:
                result[field_name] = value
            continue
        expected = _resolve_expected_type(model_field.annotation)
        if expected is None:
            # Nested Pydantic model (object with properties): UI/API often sends as JSON string
            if _is_pydantic_model_type(model_field.annotation):
                value = _unwrap_langflow_json_value(value)
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                    except json.JSONDecodeError as e:
                        msg = (
                            f"Tool '{tool_name}': Parameter '{field_name}' expects object "
                            f"but received invalid JSON string {value!r}; {e}"
                        )
                        raise ValueError(msg) from e
                    if not isinstance(parsed, dict):
                        msg = (
                            f"Tool '{tool_name}': Parameter '{field_name}' expects object "
                            f"but JSON parsed to {type(parsed).__name__}."
                        )
                        raise ValueError(msg)  # noqa: TRY004
                    value = parsed
            result[field_name] = value
            continue
        if expected is str:
            result[field_name] = value
            continue
        result[field_name] = _try_convert_value(value, expected, field_name, tool_name)
    # Preserve extra keys so Pydantic validation can report them
    result.update({k: v for k, v in arguments.items() if k not in schema_field_names})
    return result


def _handle_tool_validation_error(
    e: Exception, tool_name: str, provided_args: dict[str, Any], arg_schema: type[BaseModel]
) -> None:
    """Handle validation errors for tool arguments with detailed error messages."""
    # Check if this is a case where the tool was called with no arguments
    if not provided_args and hasattr(arg_schema, "model_fields"):
        required_fields = [name for name, field in arg_schema.model_fields.items() if field.is_required()]
        if required_fields:
            msg = (
                f"Tool '{tool_name}' requires arguments but none were provided. "
                f"Required fields: {', '.join(required_fields)}. "
                f"Please check that the LLM is properly calling the tool with arguments."
            )
            raise ValueError(msg) from e
    msg = f"Invalid input: {e}"
    raise ValueError(msg) from e


def _strip_none_recursive(obj: Any) -> Any:
    """Recursively remove None values from dicts (including inside lists).

    ``model_dump(exclude_none=True)`` handles top-level and nested-model
    None fields, but when LLMs explicitly send ``null`` for fields inside
    arrays of objects the serialised dict may still contain ``None``.
    This helper guarantees a clean payload before it reaches the MCP server.
    """
    if isinstance(obj, dict):
        return {k: _strip_none_recursive(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none_recursive(item) for item in obj]
    return obj


def _convert_mcp_result(result: Any) -> Any:
    """Convert a CallToolResult into a format LangChain agents can consume.

    - Text-only results → plain string (backward compatible).
    - Results containing images or unsupported blocks → list of LangChain
      content blocks so that vision-capable LLMs receive proper multimodal
      input instead of a raw base64 string (fixes issue #11812).
    - Unsupported block types (resource, resource_link, audio, etc.) are
      serialised as ``{"type": "text", "text": json.dumps(block)}`` so no
      content is silently dropped on the agent path.
    - Only collapses back to a plain string when every block is plain text.
    """
    if result is None:
        return ""

    content = getattr(result, "content", None)
    if not content:
        return ""

    needs_list = any(getattr(block, "type", None) != "text" for block in content)

    if not needs_list:
        # Text-only: join all text blocks into a single string (backward compat)
        return "\n".join(getattr(block, "text", "") for block in content if getattr(block, "type", None) == "text")

    # Mixed or non-text: build a list of LangChain content blocks
    blocks: list[dict] = []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            blocks.append({"type": "text", "text": getattr(block, "text", "")})
        elif block_type == "image":
            mime = getattr(block, "mimeType", None) or "image/png"
            data = getattr(block, "data", "")
            blocks.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}"},
                }
            )
        else:
            # Unsupported block type (resource, resource_link, audio, …):
            # serialise to JSON text so no content is lost on the agent path.
            try:
                raw_text = json.dumps(block.model_dump(), ensure_ascii=False)
            except AttributeError:
                raw_text = json.dumps({"type": block_type, "raw": str(block)}, ensure_ascii=False)
            blocks.append({"type": "text", "text": raw_text})
    return blocks


def create_tool_coroutine(tool_name: str, arg_schema: type[BaseModel], client) -> Callable[..., Awaitable]:
    async def tool_coroutine(*args, **kwargs):
        # Get field names from the model (preserving order)
        field_names = list(arg_schema.model_fields.keys())
        provided_args = {}
        # Map positional arguments to their corresponding field names
        for i, arg in enumerate(args):
            if i >= len(field_names):
                msg = "Too many positional arguments provided"
                raise ValueError(msg)
            provided_args[field_names[i]] = arg
        # Merge in keyword arguments
        provided_args.update(kwargs)
        provided_args = _convert_camel_case_to_snake_case(provided_args, arg_schema)
        original_args = provided_args
        provided_args = _normalize_arguments_for_mcp(provided_args, arg_schema, tool_name)
        # Validate input and fill defaults for missing optional fields
        try:
            validated = arg_schema.model_validate(provided_args)
        except Exception as e:  # noqa: BLE001
            _handle_tool_validation_error(e, tool_name, original_args, arg_schema)

        try:
            arguments = _strip_none_recursive(validated.model_dump(exclude_none=True))
            return await client.run_tool(tool_name, arguments=arguments)
        except Exception as e:
            await logger.aerror(f"Tool '{tool_name}' execution failed: {e}")
            # Re-raise with more context
            msg = f"Tool '{tool_name}' execution failed: {e}"
            raise ValueError(msg) from e

    return tool_coroutine


def create_tool_func(tool_name: str, arg_schema: type[BaseModel], client) -> Callable[..., str]:
    def tool_func(*args, **kwargs):
        field_names = list(arg_schema.model_fields.keys())
        provided_args = {}
        for i, arg in enumerate(args):
            if i >= len(field_names):
                msg = "Too many positional arguments provided"
                raise ValueError(msg)
            provided_args[field_names[i]] = arg
        provided_args.update(kwargs)
        provided_args = _convert_camel_case_to_snake_case(provided_args, arg_schema)
        original_args = provided_args
        provided_args = _normalize_arguments_for_mcp(provided_args, arg_schema, tool_name)
        try:
            validated = arg_schema.model_validate(provided_args)
        except Exception as e:  # noqa: BLE001
            _handle_tool_validation_error(e, tool_name, original_args, arg_schema)

        try:
            arguments = _strip_none_recursive(validated.model_dump(exclude_none=True))
            return run_until_complete(client.run_tool(tool_name, arguments=arguments))
        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}")
            # Re-raise with more context
            msg = f"Tool '{tool_name}' execution failed: {e}"
            raise ValueError(msg) from e

    return tool_func


def get_unique_name(base_name, max_length, existing_names):
    name = base_name[:max_length]
    if name not in existing_names:
        return name
    i = 1
    while True:
        suffix = f"_{i}"
        truncated_base = base_name[: max_length - len(suffix)]
        candidate = f"{truncated_base}{suffix}"
        if candidate not in existing_names:
            return candidate
        i += 1


async def get_flow_snake_case(flow_name: str, user_id: str, session, *, is_action: bool | None = None):
    try:
        from langflow.services.database.models.flow.model import Flow
        from sqlmodel import select
    except ImportError as e:
        msg = "Langflow Flow model is not available. This feature requires the full Langflow installation."
        raise ImportError(msg) from e

    uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id

    stmt = select(Flow).where(Flow.user_id == uuid_user_id).where(Flow.is_component == False)  # noqa: E712
    flows = (await session.exec(stmt)).all()

    for flow in flows:
        if is_action and flow.action_name:
            this_flow_name = sanitize_mcp_name(flow.action_name)
        else:
            this_flow_name = sanitize_mcp_name(flow.name)

        if this_flow_name == flow_name:
            return flow
    return None


def _is_valid_key_value_item(item: Any) -> bool:
    """Check if an item is a valid key-value dictionary."""
    return isinstance(item, dict) and "key" in item and "value" in item


def _process_headers(headers: Any, request_variables: dict[str, str] | None = None) -> dict:
    """Process the headers input into a valid dictionary and resolve global variables.

    Args:
        headers: The headers to process, can be dict, str, or list
        request_variables: Optional dict of global variables to resolve header values
    Returns:
        Processed and validated dictionary with resolved global variable values
    """
    if headers is None:
        return {}
    if isinstance(headers, dict):
        resolved_headers = _resolve_global_variables_in_headers(headers, request_variables)
        return validate_headers(resolved_headers)
    if isinstance(headers, list):
        processed_headers = {}
        try:
            for item in headers:
                if not _is_valid_key_value_item(item):
                    continue
                key = item["key"]
                value = item["value"]
                processed_headers[key] = value
        except (KeyError, TypeError, ValueError):
            return {}  # Return empty dictionary instead of None
        resolved_headers = _resolve_global_variables_in_headers(processed_headers, request_variables)
        return validate_headers(resolved_headers)
    return {}


def _resolve_global_variables_in_headers(headers: dict, request_variables: dict[str, str] | None) -> dict:
    """Resolve global variable names in header values to their actual values.

    Args:
        headers: Dictionary of headers where values might be global variable names
        request_variables: Dictionary of global variables from request context

    Returns:
        Dictionary with resolved header values
    """
    if not request_variables:
        return headers

    resolved = {}
    for key, value in headers.items():
        # If the value matches a global variable name, replace it with the actual value
        if isinstance(value, str) and value in request_variables:
            resolved[key] = request_variables[value]
        else:
            resolved[key] = value
    return resolved


def _validate_node_installation(command: str) -> str:
    """Validate the npx command."""
    if "npx" in command and not shutil.which("node"):
        msg = "Node.js is not installed. Please install Node.js to use npx commands."
        raise ValueError(msg)
    return command


async def _validate_connection_params(mode: str, command: str | None = None, url: str | None = None) -> None:
    """Validate connection parameters based on mode."""
    if mode not in ["Stdio", "Streamable_HTTP", "SSE"]:
        msg = f"Invalid mode: {mode}. Must be either 'Stdio', 'Streamable_HTTP', or 'SSE'"
        raise ValueError(msg)

    if mode == "Stdio" and not command:
        msg = "Command is required for Stdio mode"
        raise ValueError(msg)
    if mode == "Stdio" and command:
        _validate_node_installation(command)
    if mode in ["Streamable_HTTP", "SSE"] and not url:
        msg = f"URL is required for {mode} mode"
        raise ValueError(msg)


# Streamable HTTP connect: retries before giving up (transient network / server restart)
STREAMABLE_HTTP_CONNECT_ATTEMPTS = 3
STREAMABLE_HTTP_RETRY_BASE_DELAY_SEC = 0.35


def _iter_exception_leaves(exc: BaseException) -> list[BaseException]:
    """Flatten ExceptionGroup / TaskGroup failures to individual exceptions (Python 3.11+)."""
    beg = getattr(__import__("builtins"), "BaseExceptionGroup", None)
    if beg is not None and isinstance(exc, beg):
        leaves: list[BaseException] = []
        for sub in exc.exceptions:
            leaves.extend(_iter_exception_leaves(sub))
        return leaves
    return [exc]


def _is_transient_streamable_http_error(exc: BaseException) -> bool:
    """True when Streamable HTTP failed for a likely-temporary reason; do not fall back to SSE."""
    for leaf in _iter_exception_leaves(exc):
        if isinstance(leaf, (asyncio.TimeoutError, ConnectionError, OSError, BrokenPipeError)):
            return True
        if isinstance(leaf, ClosedResourceError):
            return True
        if isinstance(leaf, httpx.RequestError):
            return True
        if isinstance(leaf, httpx.HTTPStatusError):
            # Server errors and rate limits — retry Streamable HTTP, not SSE switch
            if leaf.response.status_code >= HTTP_INTERNAL_SERVER_ERROR:
                return True
            if leaf.response.status_code == HTTP_TOO_MANY_REQUESTS:
                return True
            # 404/405/406: try SSE; other 4xx: retry Streamable HTTP
            return leaf.response.status_code not in (
                HTTP_NOT_FOUND,
                HTTP_METHOD_NOT_ALLOWED,
                HTTP_NOT_ACCEPTABLE,
            )
        if isinstance(leaf, McpError):
            msg = str(leaf).lower()
            return not any(x in msg for x in ("404", "405", "406", "not found", "method not allowed"))
        msg = str(leaf).lower()
        if any(
            x in msg
            for x in (
                "session terminated",
                "connection closed",
                "connection lost",
                "connection reset",
                "taskgroup",
                "unhandled errors in a taskgroup",
                "broken pipe",
                "transport closed",
                "stream closed",
            )
        ):
            return True
    return False


def _should_attempt_sse_after_streamable_failure(exc: BaseException) -> bool:
    """True when Streamable HTTP likely failed because the endpoint expects legacy SSE, not transient outage."""
    if _is_transient_streamable_http_error(exc):
        return False
    for leaf in _iter_exception_leaves(exc):
        if isinstance(leaf, httpx.HTTPStatusError) and leaf.response.status_code in (
            HTTP_NOT_FOUND,
            HTTP_METHOD_NOT_ALLOWED,
            HTTP_NOT_ACCEPTABLE,
        ):
            return True
        if isinstance(leaf, McpError):
            msg = str(leaf).lower()
            if any(x in msg for x in ("404", "405", "406", "not found", "method not allowed", "not acceptable")):
                return True
    lowered = str(exc).lower()
    return any(x in lowered for x in ("404", "405", "406", "not found", "method not allowed", "not acceptable"))


def _is_mcp_session_bust_error(exc: BaseException) -> bool:
    """Whether cached ClientSession should be discarded and re-established (run_tool / list_tools)."""
    for leaf in _iter_exception_leaves(exc):
        if isinstance(leaf, ClosedResourceError):
            return True
        if isinstance(leaf, McpError):
            msg = str(leaf).lower()
            if any(x in msg for x in ("connection closed", "session terminated", "connection lost")):
                return True
        msg = str(leaf).lower()
        if any(x in msg for x in ("session terminated", "connection closed", "connection lost")):
            return True
    return False


class _ServerLockEntry(TypedDict):
    """Shape of each value in ``MCPSessionManager._server_locks``.

    ``pins`` is the number of callers that have obtained (but not yet
    released) the lock via ``_server_lock``; it gates reclamation of the
    entry so a new caller can't grab a fresh lock while an older caller is
    about to enter the old one.
    """

    lock: asyncio.Lock
    pins: int


# TODO(langflow-ai/langflow#12541-followup): MCPSessionManager lives in this
# 2k+ line module; extract it (and the concurrency primitives below) into a
# dedicated ``mcp/session_manager.py`` so future edits stay small.
class MCPSessionManager:
    """Manages persistent MCP sessions with proper context manager lifecycle.

    Fixed version that addresses the memory leak issue by:
    1. Session reuse based on server identity rather than unique context IDs
    2. Maximum session limits per server to prevent resource exhaustion
    3. Idle timeout for automatic session cleanup
    4. Periodic cleanup of stale sessions
    5. Transport preference caching to avoid retrying failed transports
    """

    def __init__(self):
        # Structure: server_key -> {"sessions": {session_id: session_info}, "last_cleanup": timestamp}
        self.sessions_by_server = {}
        self._background_tasks = set()  # Keep references to background tasks
        # Backwards-compatibility maps: which context_id uses which (server_key, session_id)
        self._context_to_session: dict[str, tuple[str, str]] = {}
        # Reference count for each active (server_key, session_id)
        self._session_refcount: dict[tuple[str, str], int] = {}
        # Cache which transport works for each server to avoid retrying failed transports
        # server_key -> "streamable_http" | "sse"
        self._transport_preference: dict[str, str] = {}
        # Per-server asyncio locks to serialize session create/reuse/cleanup under
        # concurrent access. Without this, two concurrent flow executions sharing
        # the same MCP server URL can race on the sessions dict and raise a
        # KeyError from `del sessions[session_id]` in `_cleanup_session_by_id`, or
        # create colliding session_ids from `len(sessions)`.
        #
        # Each entry is a `_ServerLockEntry` {"lock": asyncio.Lock(), "pins": int}.
        # The pin count is the number of callers that have obtained (but not yet
        # released) the lock via `_server_lock`. We reclaim the entry only when
        # pins == 0 and the lock is not held, to avoid a new caller grabbing a
        # fresh lock while an older caller is about to enter the old one.
        self._server_locks: dict[str, _ServerLockEntry] = {}
        self._locks_guard = asyncio.Lock()
        # Monotonic counter per server_key to generate unique session_ids even
        # when sessions are removed between allocations.
        self._session_id_counters: dict[str, int] = {}
        self._cleanup_task = None
        self._start_cleanup_task()

    @contextlib.asynccontextmanager
    async def _server_lock(self, server_key: str) -> AsyncIterator[None]:
        """Acquire the per-server lock with pin counting for safe reclamation.

        The pin count prevents reclaiming a lock that another task is about to
        enter (e.g. between obtaining a reference and calling ``async with``).
        Reclamation in `_cleanup_idle_sessions` / `_release_server_lock_if_idle`
        only runs when pins drop to zero *and* the lock is not held.
        """
        async with self._locks_guard:
            entry = self._server_locks.get(server_key)
            if entry is None:
                entry = _ServerLockEntry(lock=asyncio.Lock(), pins=0)
                self._server_locks[server_key] = entry
            entry["pins"] += 1
            lock = entry["lock"]
        try:
            async with lock:
                yield
        finally:
            await self._release_server_lock_if_idle(server_key)

    async def _release_server_lock_if_idle(self, server_key: str):
        """Drop the pin and, once the server is fully idle, reclaim the maps.

        Reclamation is deliberately conservative: we only drop the lock entry
        (and the matching session-id counter) when *both* conditions hold —
        pin count is zero and the server has no remaining sessions. This
        prevents two problems:
        - Churning the lock on every `get_session` call while a server is
          actively in use (pin count oscillates 0↔1 between callers).
        - Rotating auth/session headers (which change `server_key` via
          `_get_server_key`) leaking per-key entries forever in long-lived
          processes.
        """
        async with self._locks_guard:
            entry = self._server_locks.get(server_key)
            if entry is None:
                return
            entry["pins"] -= 1
            if entry["pins"] < 0:
                # A negative pin count means a missing acquire or a double release.
                # Log loudly so it surfaces in telemetry instead of being swept.
                await logger.awarning(
                    f"Negative pin count ({entry['pins']}) for server_key {server_key}; "
                    "this indicates a missing _server_lock acquire or a double release.",
                )
            if entry["pins"] <= 0 and not entry["lock"].locked() and server_key not in self.sessions_by_server:
                self._server_locks.pop(server_key, None)
                self._session_id_counters.pop(server_key, None)

    def _next_session_id(self, server_key: str) -> str:
        """Generate a monotonically unique session_id for *server_key*.

        Caller must hold ``self._server_lock(server_key)`` while invoking this.
        The increment is otherwise unsynchronised — two concurrent callers
        without the lock would race on ``_session_id_counters[server_key]`` and
        produce colliding ids.
        """
        current = self._session_id_counters.get(server_key, 0)
        self._session_id_counters[server_key] = current + 1
        return f"{server_key}_{current}"

    def _sessions_for(self, server_key: str) -> dict[str, dict[str, Any]]:
        """Return the sessions dict for *server_key* (empty dict if absent).

        Encapsulates the ``sessions_by_server[server_key]["sessions"]`` shape
        so callers don't have to reach through the outer envelope. Handles the
        legacy structure (sessions stored directly under the server_key)
        uniformly as well.
        """
        server_data = self.sessions_by_server.get(server_key)
        if server_data is None:
            return {}
        if isinstance(server_data, dict) and "sessions" in server_data:
            return server_data["sessions"]
        return server_data  # legacy flat structure

    def _start_cleanup_task(self):
        """Start the periodic cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self._background_tasks.add(self._cleanup_task)
            self._cleanup_task.add_done_callback(self._background_tasks.discard)

    async def _periodic_cleanup(self):
        """Periodically clean up idle sessions."""
        while True:
            try:
                await asyncio.sleep(get_session_cleanup_interval())
                await self._cleanup_idle_sessions()
            except asyncio.CancelledError:
                break
            except (RuntimeError, KeyError, ClosedResourceError, ValueError, asyncio.TimeoutError) as e:
                # Handle common recoverable errors without stopping the cleanup loop
                await logger.awarning(f"Error in periodic cleanup: {e}")

    async def _cleanup_idle_sessions(self):
        """Clean up sessions that have been idle for too long.

        Acquires the per-server lock before mutating the sessions dict so we
        don't race with `get_session()` — otherwise a concurrent `get_session`
        could finish validating a session while this task pops and cancels it,
        handing the caller a dead session plus a dangling refcount entry.
        """
        current_time = asyncio.get_event_loop().time()

        # Snapshot keys to avoid mutating-while-iterating.
        for server_key in list(self.sessions_by_server.keys()):
            async with self._server_lock(server_key):
                sessions = self._sessions_for(server_key)
                if not sessions and server_key not in self.sessions_by_server:
                    continue

                sessions_to_remove = [
                    session_id
                    for session_id, session_info in list(sessions.items())
                    if current_time - session_info["last_used"] > get_session_idle_timeout()
                ]

                for session_id in sessions_to_remove:
                    await logger.ainfo(f"Cleaning up idle session {session_id} for server {server_key}")
                    await self._cleanup_session_by_id(server_key, session_id)

                # Remove server entry if no sessions left. The counter for
                # this server_key is reclaimed by `_release_server_lock_if_idle`
                # once this lock's pin count hits zero.
                if not sessions:
                    self.sessions_by_server.pop(server_key, None)

    def _get_server_key(self, connection_params, transport_type: str) -> str:
        """Generate a consistent server key based on connection parameters."""
        if transport_type == "stdio":
            if hasattr(connection_params, "command"):
                # Include command, args, and environment for uniqueness
                command_str = f"{connection_params.command} {' '.join(connection_params.args or [])}"
                env_str = str(sorted((connection_params.env or {}).items()))
                key_input = f"{command_str}|{env_str}"
                return f"stdio_{hash(key_input)}"
        elif transport_type == "streamable_http" and (
            isinstance(connection_params, dict) and "url" in connection_params
        ):
            # Include URL and headers for uniqueness
            url = connection_params["url"]
            headers = str(sorted((connection_params.get("headers", {})).items()))
            key_input = f"{url}|{headers}"
            return f"streamable_http_{hash(key_input)}"

        # Fallback to a generic key
        return f"{transport_type}_{hash(str(connection_params))}"

    async def invalidate_server_key(self, server_key: str) -> None:
        """Tear down all sessions for this server and reset transport preference (e.g. remote MCP restart)."""
        self._transport_preference.pop(server_key, None)
        if server_key in self.sessions_by_server:
            server_data = self.sessions_by_server[server_key]
            sessions = server_data.get("sessions", {}) if isinstance(server_data, dict) else server_data
            for sid in list(sessions.keys()):
                await self._cleanup_session_by_id(server_key, sid)
            self.sessions_by_server.pop(server_key, None)
        for k in list(self._session_refcount):
            if k[0] == server_key:
                self._session_refcount.pop(k, None)
        for ctx, pair in list(self._context_to_session.items()):
            if pair[0] == server_key:
                self._context_to_session.pop(ctx, None)

    async def _validate_session_connectivity(self, session) -> bool:
        """Validate that the session is actually usable by testing a simple operation."""
        try:
            # Try to list tools as a connectivity test (this is a lightweight operation)
            # Use a shorter timeout for the connectivity test to fail fast
            response = await asyncio.wait_for(session.list_tools(), timeout=3.0)
        except Exception as e:  # noqa: BLE001
            # Any failure means the session is not safe to reuse (SDK errors, terminated session, etc.)
            await logger.adebug(f"Session connectivity test failed: {type(e).__name__}: {e}")
            return False
        else:
            # Validate that we got a meaningful response
            if response is None:
                await logger.adebug("Session connectivity test failed: received None response")
                return False
            try:
                # Check if we can access the tools list (even if empty)
                tools = getattr(response, "tools", None)
                if tools is None:
                    await logger.adebug("Session connectivity test failed: no tools attribute in response")
                    return False
            except (AttributeError, TypeError) as e:
                await logger.adebug(f"Session connectivity test failed while validating response: {e}")
                return False
            else:
                await logger.adebug(f"Session connectivity test passed: found {len(tools)} tools")
                return True

    async def get_session(self, context_id: str, connection_params, transport_type: str):
        """Get or create a session with improved reuse strategy.

        The key insight is that we should reuse sessions based on the server
        identity (command + args for stdio, URL for Streamable HTTP) rather than the context_id.
        This prevents creating a new subprocess for each unique context.

        Concurrent callers for the same server are serialized via a per-server
        lock. This is required to keep the `sessions` dict consistent across
        concurrent flow executions that share a single `MCPSessionManager`
        (e.g. two `MCPTools` components pointing at the same SSE URL).
        """
        server_key = self._get_server_key(connection_params, transport_type)

        async with self._server_lock(server_key):
            # Ensure server entry exists
            if server_key not in self.sessions_by_server:
                self.sessions_by_server[server_key] = {
                    "sessions": {},
                    "last_cleanup": asyncio.get_event_loop().time(),
                }

            server_data = self.sessions_by_server[server_key]
            sessions = server_data["sessions"]

            # Try to find a healthy existing session
            for session_id, session_info in list(sessions.items()):
                session = session_info["session"]
                task = session_info["task"]

                # Check if session is still alive
                if not task.done():
                    # Update last used time
                    session_info["last_used"] = asyncio.get_event_loop().time()

                    # Quick health check
                    if await self._validate_session_connectivity(session):
                        await logger.adebug(f"Reusing existing session {session_id} for server {server_key}")
                        # record mapping & bump ref-count for backwards compatibility
                        self._context_to_session[context_id] = (server_key, session_id)
                        self._session_refcount[(server_key, session_id)] = (
                            self._session_refcount.get((server_key, session_id), 0) + 1
                        )
                        return session
                    await logger.ainfo(f"Session {session_id} for server {server_key} failed health check, cleaning up")
                    await self._cleanup_session_by_id(server_key, session_id)
                else:
                    # Task is done, clean up
                    await logger.ainfo(f"Session {session_id} for server {server_key} task is done, cleaning up")
                    await self._cleanup_session_by_id(server_key, session_id)

            # Check if we've reached the maximum number of sessions for this server
            if len(sessions) >= get_max_sessions_per_server():
                # Remove the oldest session
                oldest_session_id = min(sessions.keys(), key=lambda x: sessions[x]["last_used"])
                await logger.ainfo(
                    f"Maximum sessions reached for server {server_key}, removing oldest session {oldest_session_id}"
                )
                await self._cleanup_session_by_id(server_key, oldest_session_id)

            # Create new session. Use a monotonic counter so removed sessions
            # don't cause id collisions with newly-created sessions.
            session_id = self._next_session_id(server_key)
            await logger.ainfo(f"Creating new session {session_id} for server {server_key}")

            if transport_type == "stdio":
                session, task = await self._create_stdio_session(session_id, connection_params)
                actual_transport = "stdio"
            elif transport_type == "streamable_http":
                # Pass the cached transport preference if available (SSE only when last success required it)
                preferred_transport = self._transport_preference.get(server_key)
                session, task, actual_transport, sse_pref_lock = await self._create_streamable_http_session(
                    session_id, connection_params, preferred_transport
                )
                if actual_transport == "streamable_http":
                    self._transport_preference[server_key] = "streamable_http"
                elif sse_pref_lock:
                    self._transport_preference[server_key] = "sse"
            else:
                msg = f"Unknown transport type: {transport_type}"
                raise ValueError(msg)

            # Store session info with the actual transport used
            sessions[session_id] = {
                "session": session,
                "task": task,
                "type": actual_transport,
                "last_used": asyncio.get_event_loop().time(),
            }

            # register mapping & initial ref-count for the new session
            self._context_to_session[context_id] = (server_key, session_id)
            self._session_refcount[(server_key, session_id)] = 1

            return session

    async def _create_stdio_session(self, session_id: str, connection_params):
        """Create a new stdio session as a background task to avoid context issues."""
        import asyncio

        from mcp.client.stdio import stdio_client

        # Create a future to get the session
        session_future: asyncio.Future[ClientSession] = asyncio.Future()

        async def session_task():
            """Background task that keeps the session alive."""
            try:
                async with stdio_client(connection_params) as (read, write):
                    session = ClientSession(read, write)
                    async with session:
                        await session.initialize()
                        # Signal that session is ready
                        session_future.set_result(session)

                        # Keep the session alive until cancelled
                        import anyio

                        event = anyio.Event()
                        try:
                            await event.wait()
                        except asyncio.CancelledError:
                            await logger.ainfo(f"Session {session_id} is shutting down")
            except Exception as e:  # noqa: BLE001
                if not session_future.done():
                    session_future.set_exception(e)

        # Start the background task
        task = asyncio.create_task(session_task())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Wait for session to be ready (use longer timeout for remote connections)
        try:
            session = await asyncio.wait_for(session_future, timeout=30.0)
        except asyncio.TimeoutError as timeout_err:
            # Clean up the failed task
            if not task.done():
                task.cancel()
                import contextlib

                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._background_tasks.discard(task)
            msg = f"Timeout waiting for STDIO session {session_id} to initialize"
            await logger.aerror(msg)
            raise ValueError(msg) from timeout_err

        return session, task

    async def _create_streamable_http_session(
        self, session_id: str, connection_params, preferred_transport: str | None = None
    ):
        """Create Streamable HTTP session with selective SSE fallback (background task lifecycle).

        SSE is attempted only when Streamable HTTP fails with an endpoint/transport mismatch signal
        (e.g. HTTP 404/405/406), not for transient outages (connection reset, TaskGroup teardown, etc.).

        Returns:
            tuple: (session, task, transport_used, sse_preference_lock) where sse_preference_lock is True
            iff SSE connected successfully and the server key should prefer legacy SSE in the future.
        """
        import asyncio

        from mcp.client.sse import sse_client
        from mcp.client.streamable_http import streamablehttp_client

        session_future: asyncio.Future[ClientSession] = asyncio.Future()
        used_transport: list[str] = []
        sse_preference_locked: list[bool] = [False]

        verify_ssl = connection_params.get("verify_ssl", True)

        def custom_httpx_factory(
            headers: dict[str, str] | None = None,
            timeout: httpx.Timeout | None = None,
            auth: httpx.Auth | None = None,
        ) -> httpx.AsyncClient:
            return create_mcp_http_client_with_ssl_option(
                headers=headers, timeout=timeout, auth=auth, verify_ssl=verify_ssl
            )

        async def session_task():
            """Background task that keeps the session alive."""
            streamable_error = None

            if preferred_transport != "sse":
                for attempt in range(STREAMABLE_HTTP_CONNECT_ATTEMPTS):
                    try:
                        await logger.adebug(
                            f"Attempting Streamable HTTP connection for session {session_id} "
                            f"(attempt {attempt + 1}/{STREAMABLE_HTTP_CONNECT_ATTEMPTS})"
                        )
                        async with streamablehttp_client(
                            url=connection_params["url"],
                            headers=connection_params["headers"],
                            timeout=connection_params["timeout_seconds"],
                            httpx_client_factory=custom_httpx_factory,
                        ) as (read, write, _):
                            session = ClientSession(read, write)
                            async with session:
                                await asyncio.wait_for(session.initialize(), timeout=2.0)
                                used_transport.append("streamable_http")
                                await logger.ainfo(f"Session {session_id} connected via Streamable HTTP")
                                session_future.set_result(session)

                                import anyio

                                event = anyio.Event()
                                try:
                                    await event.wait()
                                except asyncio.CancelledError:
                                    await logger.ainfo(f"Session {session_id} (Streamable HTTP) is shutting down")
                        return  # noqa: TRY300
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:  # noqa: BLE001
                        if _is_transient_streamable_http_error(e) and attempt < STREAMABLE_HTTP_CONNECT_ATTEMPTS - 1:
                            await logger.awarning(
                                f"Streamable HTTP transient failure for session {session_id} "
                                f"(attempt {attempt + 1}): {e}; retrying..."
                            )
                            await asyncio.sleep(STREAMABLE_HTTP_RETRY_BASE_DELAY_SEC * (attempt + 1))
                            continue
                        streamable_error = e
                        break

                if streamable_error is not None:
                    if _is_transient_streamable_http_error(streamable_error):
                        await logger.aerror(
                            f"Streamable HTTP failed after {STREAMABLE_HTTP_CONNECT_ATTEMPTS} attempt(s) "
                            f"for session {session_id}: {streamable_error}. Not attempting SSE fallback."
                        )
                        if not session_future.done():
                            session_future.set_exception(streamable_error)
                        return
                    if not _should_attempt_sse_after_streamable_failure(streamable_error):
                        if not session_future.done():
                            session_future.set_exception(streamable_error)
                        return
                    await logger.awarning(
                        f"Streamable HTTP failed for session {session_id}: {streamable_error}. "
                        "Trying SSE (endpoint may require legacy transport)..."
                    )
            else:
                await logger.adebug(f"Skipping Streamable HTTP for session {session_id}, using cached SSE preference")

            # SSE path: preferred mode, or Streamable indicated legacy transport
            try:
                await logger.adebug(f"Attempting SSE connection for session {session_id}")
                sse_read_timeout = connection_params.get("sse_read_timeout_seconds", 30)

                async with sse_client(
                    connection_params["url"],
                    connection_params["headers"],
                    connection_params["timeout_seconds"],
                    sse_read_timeout,
                    httpx_client_factory=custom_httpx_factory,
                ) as (read, write):
                    session = ClientSession(read, write)
                    async with session:
                        await session.initialize()
                        used_transport.append("sse")
                        sse_preference_locked[0] = True
                        fallback_msg = " (fallback)" if streamable_error else " (preferred)"
                        await logger.ainfo(f"Session {session_id} connected via SSE{fallback_msg}")
                        if not session_future.done():
                            session_future.set_result(session)

                        import anyio

                        event = anyio.Event()
                        try:
                            await event.wait()
                        except asyncio.CancelledError:
                            await logger.ainfo(f"Session {session_id} (SSE) is shutting down")
            except Exception as sse_error:  # noqa: BLE001
                if streamable_error:
                    await logger.aerror(
                        f"Both Streamable HTTP and SSE failed for session {session_id}. "
                        f"Streamable HTTP error: {streamable_error}. SSE error: {sse_error}"
                    )
                    if not session_future.done():
                        session_future.set_exception(
                            ValueError(
                                f"Failed to connect via Streamable HTTP ({streamable_error}) or SSE ({sse_error})"
                            )
                        )
                else:
                    await logger.aerror(f"SSE connection failed for session {session_id}: {sse_error}")
                    if not session_future.done():
                        session_future.set_exception(ValueError(f"Failed to connect via SSE: {sse_error}"))

        task = asyncio.create_task(session_task())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        try:
            session = await asyncio.wait_for(session_future, timeout=30.0)
            if used_transport:
                transport_used = used_transport[0]
                await logger.ainfo(f"Session {session_id} successfully established using {transport_used}")
                return session, task, transport_used, sse_preference_locked[0]
            msg = f"Session {session_id} established but transport not recorded"
            raise ValueError(msg)
        except asyncio.TimeoutError as timeout_err:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._background_tasks.discard(task)
            msg = f"Timeout waiting for Streamable HTTP/SSE session {session_id} to initialize"
            await logger.aerror(msg)
            raise ValueError(msg) from timeout_err

    async def _cleanup_session_by_id(self, server_key: str, session_id: str):
        """Clean up a specific session by server key and session ID.

        Safe against concurrent cleanup of the same session: we `pop` the entry
        up front so two concurrent callers don't both try to cancel the same
        task or `del` the same key (which raised `KeyError: 'streamable_http_..._0'`
        previously under concurrent flow execution).
        """
        sessions = self._sessions_for(server_key)
        if not sessions and server_key not in self.sessions_by_server:
            return

        # Atomically remove the session entry; only the caller that wins this
        # pop performs the actual teardown. Concurrent callers get None and
        # return early instead of racing on del/task.cancel().
        session_info = sessions.pop(session_id, None)
        if session_info is None:
            return

        try:
            # First try to properly close the session if it exists
            if "session" in session_info:
                session = session_info["session"]

                # Try async close first (aclose method)
                if hasattr(session, "aclose"):
                    try:
                        await session.aclose()
                        await logger.adebug("Successfully closed session %s using aclose()", session_id)
                    except Exception as e:  # noqa: BLE001
                        await logger.adebug("Error closing session %s with aclose(): %s", session_id, e)

                # If no aclose, try regular close method
                elif hasattr(session, "close"):
                    try:
                        # Check if close() is awaitable using inspection
                        if inspect.iscoroutinefunction(session.close):
                            # It's an async method
                            await session.close()
                            await logger.adebug("Successfully closed session %s using async close()", session_id)
                        else:
                            # Try calling it and check if result is awaitable
                            close_result = session.close()
                            if inspect.isawaitable(close_result):
                                await close_result
                                await logger.adebug(
                                    "Successfully closed session %s using awaitable close()", session_id
                                )
                            else:
                                # It's a synchronous close
                                await logger.adebug("Successfully closed session %s using sync close()", session_id)
                    except Exception as e:  # noqa: BLE001
                        await logger.adebug("Error closing session %s with close(): %s", session_id, e)

            # Cancel the background task which will properly close the session
            if "task" in session_info:
                task = session_info["task"]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        await logger.ainfo(f"Cancelled task for session {session_id}")
        except Exception as e:  # noqa: BLE001
            # Teardown is load-bearing: MCP transports (stdio subprocess, SSE,
            # streamable HTTP) all raise their own exception hierarchies on
            # shutdown, and a leak on cleanup is far worse than a swallowed
            # error. Log and continue rather than propagating.
            await logger.awarning(f"Error cleaning up session {session_id}: {e}")

    async def cleanup_all(self):
        """Clean up all sessions."""
        # Cancel periodic cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        # Clean up all sessions
        for server_key in list(self.sessions_by_server.keys()):
            for session_id in list(self._sessions_for(server_key).keys()):
                await self._cleanup_session_by_id(server_key, session_id)

        # Clear the sessions_by_server structure completely
        self.sessions_by_server.clear()

        # Clear compatibility maps
        self._context_to_session.clear()
        self._session_refcount.clear()

        # Reclaim per-server lock and counter maps. Safe here because
        # cleanup_all is a shutdown/reset operation; no other manager state
        # should be in use past this point.
        async with self._locks_guard:
            self._server_locks.clear()
            self._session_id_counters.clear()

        # Clear all background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        # Give a bit more time for subprocess transports to clean up
        # This helps prevent the BaseSubprocessTransport.__del__ warnings
        await asyncio.sleep(0.5)

    async def _cleanup_session(self, context_id: str):
        """Backward-compat cleanup by context_id.

        Decrements the ref-count for the session used by *context_id* and only
        tears the session down when the last context that references it goes
        away.

        Acquires the per-server lock so concurrent `get_session()` calls don't
        observe a half-torn-down session (e.g. returning a ClientSession whose
        background task was just cancelled out from under them).

        Uses a compare-and-swap on `_context_to_session[context_id]` before
        popping it: if a concurrent `get_session()` has re-pointed the same
        context at a *different* server (e.g. a component reconnecting to a
        new MCP URL while the old disconnect is in flight), we must not wipe
        out the fresh mapping — otherwise the new session leaks. The per-
        server lock doesn't cover this case because the new and old sessions
        live under different server_keys, so the two operations run in
        parallel.
        """
        mapping = self._context_to_session.get(context_id)
        if not mapping:
            await logger.adebug(f"No session mapping found for context_id {context_id}")
            return

        server_key, session_id = mapping
        async with self._server_lock(server_key):
            ref_key = (server_key, session_id)
            remaining = self._session_refcount.get(ref_key, 1) - 1

            if remaining <= 0:
                await self._cleanup_session_by_id(server_key, session_id)
                self._session_refcount.pop(ref_key, None)
            else:
                self._session_refcount[ref_key] = remaining

            # CAS: only drop the context->session mapping if it still points
            # at the session we just cleaned up. The get() and pop() below run
            # synchronously with no `await` between them, so no other coroutine
            # can interleave and re-point the mapping after our check.
            if self._context_to_session.get(context_id) == (server_key, session_id):
                self._context_to_session.pop(context_id, None)


class MCPStdioClient:
    def __init__(self, component_cache=None, tool_execution_timeout: float | None = None):
        self.session: ClientSession | None = None
        self._connection_params = None
        self._connected = False
        self._session_context: str | None = None
        self._component_cache = component_cache
        self._tool_execution_timeout = _resolve_mcp_tool_execution_timeout(tool_execution_timeout)

    async def _connect_to_server(self, command_str: str, env: dict[str, str] | None = None) -> list[StructuredTool]:
        """Connect to MCP server using stdio transport (SDK style).

        The server process is launched **without a shell** (``shell=False``
        semantics): ``command_str`` is tokenized with :func:`shlex.split` and
        the resulting executable + arguments are passed to
        :class:`~mcp.StdioServerParameters` directly.  The MCP SDK then execs
        the process via ``anyio.open_process`` on POSIX and
        ``create_windows_process`` on Windows -- the latter resolving ``.cmd`` /
        ``.bat`` / ``.exe`` wrappers (e.g. ``npx.cmd``) through ``shutil.which``
        -- so no ``bash -c`` / ``cmd /c`` wrapper is required on any platform.

        Removing the shell wrapper structurally eliminates the entire class of
        injection vectors that depend on a shell interpreter starting up:
        shell metacharacters, ``IFS`` word-splitting, ``CDPATH`` redirection,
        ``BASH_ENV`` / ``ENV`` / ``BASH_FUNC_*`` startup injection, and
        ``PS4`` / ``SHELLOPTS`` xtrace abuse.  None of those can fire because no
        shell is ever spawned.  The :func:`_validate_mcp_stdio_env` backstop
        still rejects loader and interpreter env vars (``LD_PRELOAD``,
        ``DYLD_*``, ``GCONV_PATH``, ``PYTHONPATH``, ``NODE_OPTIONS``, ...) which
        remain dangerous regardless of the shell because they are honored by the
        dynamic linker or the target interpreter itself.
        """
        from mcp import StdioServerParameters

        command_parts = shlex.split(command_str)
        if not command_parts:
            msg = "MCP stdio command is empty"
            raise ValueError(msg)

        safe_env = _validate_mcp_stdio_env(env)
        env_data: dict[str, str] = {"DEBUG": "true", "PATH": os.environ["PATH"], **safe_env}

        # shell=False: exec the binary directly with structured args. The MCP SDK
        # abstracts the platform differences (POSIX exec vs. Windows executable
        # resolution), so identical parameters work on every OS and no shell
        # interpreter is ever interposed between Langflow and the server process.
        server_params = StdioServerParameters(
            command=command_parts[0],
            args=command_parts[1:],
            env=env_data,
        )

        # Store connection parameters for later use in run_tool
        self._connection_params = server_params

        # If no session context is set, create a default one
        if not self._session_context:
            # Generate a fallback context based on connection parameters
            import uuid

            param_hash = uuid.uuid4().hex[:8]
            self._session_context = f"default_{param_hash}"

        # Get or create a persistent session
        session = await self._get_or_create_session()
        response = await session.list_tools()
        self._connected = True
        return response.tools

    async def connect_to_server(self, command_str: str, env: dict[str, str] | None = None) -> list[StructuredTool]:
        """Connect to MCP server using stdio transport (SDK style)."""
        return await asyncio.wait_for(
            self._connect_to_server(command_str, env), timeout=get_settings_service().settings.mcp_server_timeout
        )

    def set_session_context(self, context_id: str):
        """Set the session context (e.g., flow_id + user_id + session_id)."""
        self._session_context = context_id

    def _get_session_manager(self) -> MCPSessionManager:
        """Get or create session manager from component cache."""
        if not self._component_cache:
            # Fallback to instance-level session manager if no cache
            if not hasattr(self, "_session_manager"):
                self._session_manager = MCPSessionManager()
            return self._session_manager

        from lfx.services.cache.utils import CacheMiss

        session_manager = self._component_cache.get("mcp_session_manager")
        if isinstance(session_manager, CacheMiss):
            session_manager = MCPSessionManager()
            self._component_cache.set("mcp_session_manager", session_manager)
        return session_manager

    async def _get_or_create_session(self) -> ClientSession:
        """Get or create a persistent session for the current context."""
        if not self._session_context or not self._connection_params:
            msg = "Session context and connection params must be set"
            raise ValueError(msg)

        # Use cached session manager to get/create persistent session
        session_manager = self._get_session_manager()
        return await session_manager.get_session(self._session_context, self._connection_params, "stdio")

    async def run_tool(self, tool_name: str, arguments: dict[str, Any], timeout: float | None = None) -> Any:  # noqa: ASYNC109
        """Run a tool with the given arguments using context-specific session.

        Args:
            tool_name: Name of the tool to run
            arguments: Dictionary of arguments to pass to the tool
            timeout: Optional timeout in seconds. If not provided, uses the client's configured timeout.

        Returns:
            The result of the tool execution

        Raises:
            ValueError: If session is not initialized or tool execution fails
        """
        if not self._connected or not self._connection_params:
            msg = "Session not initialized or disconnected. Call connect_to_server first."
            raise ValueError(msg)

        # If no session context is set, create a default one
        if not self._session_context:
            # Generate a fallback context based on connection parameters
            import uuid

            param_hash = uuid.uuid4().hex[:8]
            self._session_context = f"default_{param_hash}"

        # Use provided timeout or fall back to client's configured timeout
        effective_timeout = timeout if timeout is not None else self._tool_execution_timeout

        max_retries = 2
        last_error_type = None

        for attempt in range(max_retries):
            try:
                await logger.adebug(f"Attempting to run tool '{tool_name}' (attempt {attempt + 1}/{max_retries})")
                # Get or create persistent session
                session = await self._get_or_create_session()

                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=effective_timeout,
                )
            except Exception as e:
                current_error_type = type(e).__name__
                await logger.awarning(f"Tool '{tool_name}' failed on attempt {attempt + 1}: {current_error_type} - {e}")

                # Import specific MCP error types for detection
                try:
                    is_closed_resource_error = isinstance(e, ClosedResourceError)
                    is_mcp_connection_error = isinstance(e, McpError) and "Connection closed" in str(e)
                except ImportError:
                    is_closed_resource_error = "ClosedResourceError" in str(type(e))
                    is_mcp_connection_error = "Connection closed" in str(e)

                # Detect timeout errors
                is_timeout_error = isinstance(e, asyncio.TimeoutError | TimeoutError)

                # If we're getting the same error type repeatedly, don't retry
                if last_error_type == current_error_type and attempt > 0:
                    await logger.aerror(f"Repeated {current_error_type} error for tool '{tool_name}', not retrying")
                    break

                last_error_type = current_error_type

                # If it's a connection error (ClosedResourceError or MCP connection closed) and we have retries left
                if (is_closed_resource_error or is_mcp_connection_error) and attempt < max_retries - 1:
                    await logger.awarning(
                        f"MCP session connection issue for tool '{tool_name}', retrying with fresh session..."
                    )
                    # Clean up the dead session
                    if self._session_context:
                        session_manager = self._get_session_manager()
                        await session_manager._cleanup_session(self._session_context)
                    # Add a small delay before retry
                    await asyncio.sleep(0.5)
                    continue

                # If it's a timeout error and we have retries left, try once more
                if is_timeout_error and attempt < max_retries - 1:
                    await logger.awarning(f"Tool '{tool_name}' timed out, retrying...")
                    # Don't clean up session for timeouts, might just be a slow response
                    await asyncio.sleep(1.0)
                    continue

                # For other errors or no retries left, handle as before
                if (
                    isinstance(e, ConnectionError | TimeoutError | OSError | ValueError)
                    or is_closed_resource_error
                    or is_mcp_connection_error
                    or is_timeout_error
                ):
                    msg = f"Failed to run tool '{tool_name}' after {attempt + 1} attempts: {e}"
                    await logger.aerror(msg)
                    # Clean up failed session from cache
                    if self._session_context and self._component_cache:
                        cache_key = f"mcp_session_stdio_{self._session_context}"
                        self._component_cache.delete(cache_key)
                    self._connected = False
                    raise ValueError(msg) from e
                # Re-raise unexpected errors
                raise
            else:
                await logger.adebug(f"Tool '{tool_name}' completed successfully")
                return result

        # This should never be reached due to the exception handling above
        msg = f"Failed to run tool '{tool_name}': Maximum retries exceeded with repeated {last_error_type} errors"
        await logger.aerror(msg)
        raise ValueError(msg)

    async def disconnect(self):
        """Properly close the connection and clean up resources."""
        # For stdio transport, there is no remote session to terminate explicitly
        # The session cleanup happens when the background task is cancelled

        # Clean up local session using the session manager
        if self._session_context:
            session_manager = self._get_session_manager()
            await session_manager._cleanup_session(self._session_context)

        # Reset local state
        self.session = None
        self._connection_params = None
        self._connected = False
        self._session_context = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


class MCPStreamableHttpClient:
    def __init__(self, component_cache=None, tool_execution_timeout: float | None = None):
        self.session: ClientSession | None = None
        self._connection_params = None
        self._connected = False
        self._session_context: str | None = None
        self._component_cache = component_cache
        self._tool_execution_timeout = _resolve_mcp_tool_execution_timeout(tool_execution_timeout)

    def _get_session_manager(self) -> MCPSessionManager:
        """Get or create session manager from component cache."""
        if not self._component_cache:
            # Fallback to instance-level session manager if no cache
            if not hasattr(self, "_session_manager"):
                self._session_manager = MCPSessionManager()
            return self._session_manager

        from lfx.services.cache.utils import CacheMiss

        session_manager = self._component_cache.get("mcp_session_manager")
        if isinstance(session_manager, CacheMiss):
            session_manager = MCPSessionManager()
            self._component_cache.set("mcp_session_manager", session_manager)
        return session_manager

    async def validate_url(self, url: str | None) -> tuple[bool, str]:
        """Validate the Streamable HTTP URL before attempting connection."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format. Must include scheme (http/https) and host."
        except (ValueError, OSError) as e:
            return False, f"URL validation error: {e!s}"
        return True, ""

    async def _connect_to_server(
        self,
        url: str | None,
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 30,
        sse_read_timeout_seconds: int = 30,
        *,
        verify_ssl: bool = True,
    ) -> list[StructuredTool]:
        """Connect to MCP server using Streamable HTTP transport with SSE fallback (SDK style)."""
        # Validate and sanitize headers early
        validated_headers = _process_headers(headers)

        if url is None:
            msg = "URL is required for StreamableHTTP or SSE mode"
            raise ValueError(msg)

        # Only validate URL if we don't have a cached session
        # This avoids expensive HTTP validation calls when reusing sessions
        if not self._connected or not self._connection_params:
            is_valid, error_msg = await self.validate_url(url)
            if not is_valid:
                msg = f"Invalid Streamable HTTP or SSE URL ({url}): {error_msg}"
                raise ValueError(msg)
            # Store connection parameters for later use in run_tool
            # Include SSE read timeout for fallback and SSL verification option
            self._connection_params = {
                "url": url,
                "headers": validated_headers,
                "timeout_seconds": timeout_seconds,
                "sse_read_timeout_seconds": sse_read_timeout_seconds,
                "verify_ssl": verify_ssl,
            }
        elif headers:
            self._connection_params["headers"] = validated_headers

        # If no session context is set, create a default one
        if not self._session_context:
            # Generate a fallback context based on connection parameters
            import uuid

            param_hash = uuid.uuid4().hex[:8]
            self._session_context = f"default_http_{param_hash}"

        # Get or create a persistent session (will try Streamable HTTP, then selective SSE fallback)
        session = await self._get_or_create_session()
        try:
            response = await session.list_tools()
        except Exception:
            self._connected = False
            if self._connection_params:
                session_manager = self._get_session_manager()
                sk = session_manager._get_server_key(self._connection_params, "streamable_http")
                await session_manager.invalidate_server_key(sk)
            raise
        self._connected = True
        return response.tools

    async def connect_to_server(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        sse_read_timeout_seconds: int = 30,
        *,
        verify_ssl: bool = True,
    ) -> list[StructuredTool]:
        """Connect to MCP server using Streamable HTTP with SSE fallback transport (SDK style)."""
        return await asyncio.wait_for(
            self._connect_to_server(
                url, headers, sse_read_timeout_seconds=sse_read_timeout_seconds, verify_ssl=verify_ssl
            ),
            timeout=get_settings_service().settings.mcp_server_timeout,
        )

    def set_session_context(self, context_id: str):
        """Set the session context (e.g., flow_id + user_id + session_id)."""
        self._session_context = context_id

    async def _get_or_create_session(self) -> ClientSession:
        """Get or create a persistent session for the current context."""
        if not self._session_context or not self._connection_params:
            msg = "Session context and params must be set"
            raise ValueError(msg)

        # Use cached session manager to get/create persistent session
        session_manager = self._get_session_manager()
        # Cache session so we can access server-assigned session_id later for DELETE
        self.session = await session_manager.get_session(
            self._session_context, self._connection_params, "streamable_http"
        )
        return self.session

    async def _terminate_remote_session(self) -> None:
        """Attempt to explicitly terminate the remote MCP session via HTTP DELETE (best-effort)."""
        # Only relevant for Streamable HTTP or SSE transport
        if not self._connection_params or "url" not in self._connection_params:
            return

        url: str = self._connection_params["url"]

        # Retrieve session id from the underlying SDK if exposed
        session_id = None
        if getattr(self, "session", None) is not None:
            # Common attributes in MCP python SDK: `session_id` or `id`
            session_id = getattr(self.session, "session_id", None) or getattr(self.session, "id", None)

        headers: dict[str, str] = dict(self._connection_params.get("headers", {}))
        if session_id:
            headers["Mcp-Session-Id"] = str(session_id)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.delete(url, headers=headers)
        except Exception as e:  # noqa: BLE001
            # DELETE is advisory—log and continue
            logger.debug(f"Unable to send session DELETE to '{url}': {e}")

    async def run_tool(self, tool_name: str, arguments: dict[str, Any], timeout: float | None = None) -> Any:  # noqa: ASYNC109
        """Run a tool with the given arguments using context-specific session.

        Args:
            tool_name: Name of the tool to run
            arguments: Dictionary of arguments to pass to the tool
            timeout: Optional timeout in seconds. If not provided, uses the client's configured timeout.

        Returns:
            The result of the tool execution

        Raises:
            ValueError: If session is not initialized or tool execution fails
        """
        if not self._connected or not self._connection_params:
            msg = "Session not initialized or disconnected. Call connect_to_server first."
            raise ValueError(msg)

        # If no session context is set, create a default one
        if not self._session_context:
            # Generate a fallback context based on connection parameters
            import uuid

            param_hash = uuid.uuid4().hex[:8]
            self._session_context = f"default_http_{param_hash}"

        # Use provided timeout or fall back to client's configured timeout
        effective_timeout = timeout if timeout is not None else self._tool_execution_timeout

        max_retries = 2
        last_error_type = None

        for attempt in range(max_retries):
            try:
                await logger.adebug(f"Attempting to run tool '{tool_name}' (attempt {attempt + 1}/{max_retries})")
                # Get or create persistent session
                session = await self._get_or_create_session()

                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=effective_timeout,
                )
            except Exception as e:
                current_error_type = type(e).__name__
                await logger.awarning(f"Tool '{tool_name}' failed on attempt {attempt + 1}: {current_error_type} - {e}")

                bust_session = _is_mcp_session_bust_error(e)

                # Detect timeout errors
                is_timeout_error = isinstance(e, asyncio.TimeoutError | TimeoutError)

                # If we're getting the same error type repeatedly, don't retry
                if last_error_type == current_error_type and attempt > 0:
                    await logger.aerror(f"Repeated {current_error_type} error for tool '{tool_name}', not retrying")
                    break

                last_error_type = current_error_type

                if bust_session and attempt < max_retries - 1:
                    await logger.awarning(
                        f"MCP session issue for tool '{tool_name}', invalidating server sessions and retrying..."
                    )
                    if self._connection_params:
                        session_manager = self._get_session_manager()
                        sk = session_manager._get_server_key(self._connection_params, "streamable_http")
                        await session_manager.invalidate_server_key(sk)
                    await asyncio.sleep(0.5)
                    continue

                # If it's a timeout error and we have retries left, try once more
                if is_timeout_error and attempt < max_retries - 1:
                    await logger.awarning(f"Tool '{tool_name}' timed out, retrying...")
                    # Don't clean up session for timeouts, might just be a slow response
                    await asyncio.sleep(1.0)
                    continue

                # For other errors or no retries left, handle as before
                if (
                    isinstance(e, ConnectionError | TimeoutError | OSError | ValueError)
                    or bust_session
                    or is_timeout_error
                ):
                    msg = f"Failed to run tool '{tool_name}' after {attempt + 1} attempts: {e}"
                    await logger.aerror(msg)
                    # Clean up failed session from cache
                    if self._session_context and self._component_cache:
                        cache_key = f"mcp_session_http_{self._session_context}"
                        self._component_cache.delete(cache_key)
                    self._connected = False
                    raise ValueError(msg) from e
                # Re-raise unexpected errors
                raise
            else:
                await logger.adebug(f"Tool '{tool_name}' completed successfully")
                return result

        # This should never be reached due to the exception handling above
        msg = f"Failed to run tool '{tool_name}': Maximum retries exceeded with repeated {last_error_type} errors"
        await logger.aerror(msg)
        raise ValueError(msg)

    async def disconnect(self):
        """Properly close the connection and clean up resources."""
        # Attempt best-effort remote session termination first
        await self._terminate_remote_session()

        # Clean up local session using the session manager
        if self._session_context:
            session_manager = self._get_session_manager()
            await session_manager._cleanup_session(self._session_context)

        # Reset local state
        self.session = None
        self._connection_params = None
        self._connected = False
        self._session_context = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# Backward compatibility: MCPSseClient is now an alias for MCPStreamableHttpClient
# The new client supports both Streamable HTTP and SSE with automatic fallback
MCPSseClient = MCPStreamableHttpClient


async def update_tools(
    server_name: str,
    server_config: dict,
    mcp_stdio_client: MCPStdioClient | None = None,
    mcp_streamable_http_client: MCPStreamableHttpClient | None = None,
    mcp_sse_client: MCPStreamableHttpClient | None = None,  # Backward compatibility
    request_variables: dict[str, str] | None = None,
    tool_execution_timeout: float | None = None,
) -> tuple[str, list[StructuredTool], dict[str, StructuredTool]]:
    """Fetch server config and update available tools.

    Args:
        server_name: Name of the MCP server
        server_config: Server configuration dictionary
        mcp_stdio_client: Optional stdio client instance
        mcp_streamable_http_client: Optional streamable HTTP client instance
        mcp_sse_client: Optional SSE client instance (backward compatibility)
        request_variables: Optional dict of global variables to resolve in headers
        tool_execution_timeout: Optional timeout in seconds for tool execution (int or float)
    """
    if server_config is None:
        server_config = {}
    if not server_name:
        return "", [], {}

    if mcp_stdio_client is None:
        mcp_stdio_client = MCPStdioClient(tool_execution_timeout=tool_execution_timeout)
    # Update timeout on existing client only if a new timeout is provided.
    # Route through _resolve_mcp_tool_execution_timeout so that negative values
    # (entered before UI validation fires) never reach asyncio.wait_for.
    elif tool_execution_timeout is not None:
        mcp_stdio_client._tool_execution_timeout = _resolve_mcp_tool_execution_timeout(tool_execution_timeout)

    # Backward compatibility: accept mcp_sse_client parameter
    if mcp_streamable_http_client is None:
        if mcp_sse_client is not None:
            mcp_streamable_http_client = mcp_sse_client
            # Set timeout on the aliased client if provided
            if tool_execution_timeout is not None:
                mcp_streamable_http_client._tool_execution_timeout = _resolve_mcp_tool_execution_timeout(
                    tool_execution_timeout
                )
        else:
            mcp_streamable_http_client = MCPStreamableHttpClient(tool_execution_timeout=tool_execution_timeout)
    # Update timeout on existing client only if a new timeout is provided
    elif tool_execution_timeout is not None:
        mcp_streamable_http_client._tool_execution_timeout = _resolve_mcp_tool_execution_timeout(tool_execution_timeout)

    # Fetch server config from backend
    # Determine mode from config, defaulting to Streamable_HTTP if URL present
    mode = server_config.get("mode", "")
    if not mode:
        mode = "Stdio" if "command" in server_config else "Streamable_HTTP" if "url" in server_config else ""

    command = server_config.get("command", "")
    url = server_config.get("url", "")
    tools = []
    headers = _process_headers(server_config.get("headers", {}), request_variables)

    try:
        await _validate_connection_params(mode, command, url)
    except ValueError as e:
        logger.error(f"Invalid MCP server configuration for '{server_name}': {e}")
        raise

    # Determine connection type and parameters
    client: MCPStdioClient | MCPStreamableHttpClient | None = None
    if mode == "Stdio":
        args = list(server_config.get("args", []))
        env = server_config.get("env", {})
        # For stdio mode, inject component headers as --headers CLI args.
        # This enables passing headers through proxy tools like mcp-proxy
        # that forward them to the upstream HTTP server.
        if headers:
            extra_args = []
            for key, value in headers.items():
                extra_args.extend(["--headers", key, str(value)])
            if "--headers" in args:
                # Insert before the existing --headers flag so all header
                # flags are grouped together
                idx = args.index("--headers")
                for i, arg in enumerate(extra_args):
                    args.insert(idx + i, arg)
            else:
                # No existing --headers flag; try to insert before the last
                # positional arg (typically the URL in mcp-proxy commands).
                # Scan args to find the last true positional token by skipping
                # flag+value pairs so we don't mistake a flag's value for a
                # positional argument (e.g. "--port 8080").
                last_positional_idx: int | None = None
                i = 0
                while i < len(args):
                    if args[i].startswith("-"):
                        # Skip the flag and its value (assumes each flag
                        # takes at most one value argument; boolean flags
                        # are handled correctly since the next token will
                        # start with '-' or be a URL-like positional).
                        i += 1
                        if (
                            i < len(args)
                            and not args[i].startswith("-")
                            and not args[i].startswith("http://")
                            and not args[i].startswith("https://")
                        ):
                            i += 1
                    else:
                        last_positional_idx = i
                        i += 1

                if last_positional_idx is not None:
                    args = args[:last_positional_idx] + extra_args + args[last_positional_idx:]
                else:
                    args.extend(extra_args)
        full_command = shlex.join([*shlex.split(command), *args])
        tools = await mcp_stdio_client.connect_to_server(full_command, env)
        client = mcp_stdio_client
    elif mode in ["Streamable_HTTP", "SSE"]:
        # Streamable HTTP connection with SSE fallback
        verify_ssl = server_config.get("verify_ssl", True)
        tools = await mcp_streamable_http_client.connect_to_server(url, headers=headers, verify_ssl=verify_ssl)
        client = mcp_streamable_http_client
    else:
        logger.error(f"Invalid MCP server mode for '{server_name}': {mode}")
        return "", [], {}

    if not tools or not client or not client._connected:
        logger.warning(f"No tools available from MCP server '{server_name}' or connection failed")
        return "", [], {}

    tool_list = []
    tool_cache: dict[str, StructuredTool] = {}
    for tool in tools:
        if not tool or not hasattr(tool, "name"):
            continue
        try:
            args_schema = create_input_schema_from_json_schema(tool.inputSchema)
            if not args_schema:
                logger.warning(f"Could not create schema for tool '{tool.name}' from server '{server_name}'")
                continue

            # Create a custom StructuredTool that bypasses schema validation
            class MCPStructuredTool(StructuredTool):
                _tool_call_id_key = "_lf_tool_call_id"

                def _to_args_and_kwargs(
                    self, tool_input: str | dict, tool_call_id: str | None
                ) -> tuple[tuple, dict[str, Any]]:
                    """Normalize MCP tool input before LangChain validates it."""
                    if isinstance(tool_input, str):
                        try:
                            parsed_input = json.loads(tool_input)
                        except json.JSONDecodeError:
                            parsed_input = {"input": tool_input}
                    else:
                        parsed_input = tool_input or {}

                    converted_input = self._convert_parameters(parsed_input)
                    tool_args, tool_kwargs = super()._to_args_and_kwargs(converted_input, tool_call_id)
                    if tool_call_id is not None:
                        tool_kwargs[self._tool_call_id_key] = tool_call_id
                    return tool_args, tool_kwargs

                def _run(self, *args: Any, config: RunnableConfig, run_manager=None, **kwargs: Any) -> tuple[Any, Any]:
                    """Return converted content plus the raw MCP result as artifact."""
                    tool_call_id = kwargs.pop(self._tool_call_id_key, None)
                    raw = super()._run(*args, config=config, run_manager=run_manager, **kwargs)
                    content = _convert_mcp_result(raw) if tool_call_id and hasattr(raw, "content") else raw
                    return content, raw

                async def _arun(
                    self, *args: Any, config: RunnableConfig, run_manager=None, **kwargs: Any
                ) -> tuple[Any, Any]:
                    """Return converted content plus the raw MCP result as artifact."""
                    tool_call_id = kwargs.pop(self._tool_call_id_key, None)
                    raw = await super()._arun(*args, config=config, run_manager=run_manager, **kwargs)
                    content = _convert_mcp_result(raw) if tool_call_id and hasattr(raw, "content") else raw
                    return content, raw

                def _convert_parameters(self, input_dict):
                    if not input_dict or not isinstance(input_dict, dict):
                        return input_dict

                    converted_dict = {}
                    original_fields = set(self.args_schema.model_fields.keys())

                    for key, value in input_dict.items():
                        if key in original_fields:
                            # Field exists as-is
                            converted_dict[key] = value
                        else:
                            # Try to convert camelCase to snake_case
                            snake_key = _camel_to_snake(key)
                            if snake_key in original_fields:
                                converted_dict[snake_key] = value
                            else:
                                # Keep original key (may be flattened e.g. params.search)
                                converted_dict[key] = value

                    unflattened = maybe_unflatten_dict(converted_dict)
                    # Normalize: convert JSON strings to dict for nested model params
                    normalized = _normalize_arguments_for_mcp(unflattened, self.args_schema, self.name)
                    # Preserve extra keys not in schema (e.g. flattened keys)
                    schema_fields = set(self.args_schema.model_fields.keys())
                    for key, value in unflattened.items():
                        if key not in schema_fields and key not in normalized:
                            normalized[key] = value
                    return normalized

            tool_obj = MCPStructuredTool(
                name=tool.name,
                description=tool.description or "",
                args_schema=args_schema,
                func=create_tool_func(tool.name, args_schema, client),
                coroutine=create_tool_coroutine(tool.name, args_schema, client),
                tags=[tool.name],
                metadata={"server_name": server_name, "output_schema": getattr(tool, "outputSchema", None)},
                response_format="content_and_artifact",
            )

            tool_list.append(tool_obj)
            tool_cache[tool.name] = tool_obj
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Failed to create tool '{tool.name}' from server '{server_name}': {e}")
            msg = f"Failed to create tool '{tool.name}' from server '{server_name}': {e}"
            raise ValueError(msg) from e
        except (TypeError, AttributeError, KeyError, NameError, RecursionError) as e:
            # Per-tool resilience (#11229): isolate one bad schema, keep the rest of the toolset.
            logger.exception(
                f"Skipping tool '{getattr(tool, 'name', '<unknown>')}' from MCP server "
                f"'{server_name}' due to schema-processing error: "
                f"{type(e).__name__}: {e}. inputSchema={getattr(tool, 'inputSchema', None)!r}"
            )
            continue

    logger.info(f"Successfully loaded {len(tool_list)} tools from MCP server '{server_name}'")
    return mode, tool_list, tool_cache
