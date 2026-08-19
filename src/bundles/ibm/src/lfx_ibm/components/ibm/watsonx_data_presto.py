"""Query IBM watsonx.data through its Presto engine (DBAPI) and return a DataFrame."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.dataframe import DataFrame
from lfx.utils.file_path_security import component_file_access_scopes
from lfx.utils.ssrf_protection import validate_connector_url_for_ssrf
from lfx_ibm.components.ibm.db2_security import (
    create_safe_error_message,
    validate_and_prepare_ssl_certificate,
    validate_hostname,
    validate_port,
)

AUTH_API_KEY = "api_key"  # pragma: allowlist secret -- option name, not a credential
AUTH_BASIC = "basic"
AUTH_OPTIONS = [AUTH_API_KEY, AUTH_BASIC]

# watsonx.data (SaaS) authenticates Presto clients with the fixed user name
# ``ibmlhapikey`` and an IBM Cloud IAM API key as the password.
DEFAULT_API_KEY_USERNAME = "ibmlhapikey"  # pragma: allowlist secret -- fixed Presto user name, not a credential
DEFAULT_PORT = 443
DEFAULT_MAX_ROWS = 10_000
MAX_ROWS_CAP = 1_000_000
DEFAULT_REQUEST_TIMEOUT = 60.0


def _unique_columns(columns: list[str]) -> list[str]:
    """Return ``columns`` with duplicates suffixed, so no row value is lost.

    A row is turned into a dict, and SQL happily returns the same column name twice
    (``SELECT a.id, b.id FROM ...``); without renaming, the later value would silently
    overwrite the earlier one.
    """
    seen: dict[str, int] = {}
    unique: list[str] = []
    for column in columns:
        count = seen.get(column, 0)
        seen[column] = count + 1
        if count:
            name = f"{column}_{count}"
            while name in seen:
                count += 1
                seen[column] = count + 1
                name = f"{column}_{count}"
            seen[name] = 1
            unique.append(name)
        else:
            unique.append(column)
    return unique


class WatsonxDataPrestoComponent(Component):
    """Run SQL against watsonx.data Presto (Java or C++) and return the rows as a table.

    Works for watsonx.data on IBM Cloud (API-key auth as ``ibmlhapikey``) and
    for watsonx.data software (basic auth with the credentials your instance
    expects, plus the instance CA certificate).  Tableflow tables registered
    in watsonx.data as an Iceberg REST datasource are queried the same way as
    any other catalog.
    """

    display_name = "IBM watsonx.data Presto"
    description = (
        "Execute a SQL query on an IBM watsonx.data Presto engine (Iceberg lakehouse, federated "
        "sources, Confluent Tableflow tables) and return the result as a DataFrame."
    )
    documentation: str = "https://docs.langflow.org/bundles-ibm"
    icon = "WatsonxData"
    name = "WatsonxDataPresto"
    metadata = {"keywords": ["ibm", "watsonx", "watsonx.data", "presto", "sql", "lakehouse", "iceberg", "streamhouse"]}

    inputs = [
        StrInput(
            name="host",
            display_name="Presto Host",
            info="Presto engine host name (from the watsonx.data engine details, without https://).",
            required=True,
        ),
        IntInput(
            name="port",
            display_name="Port",
            value=DEFAULT_PORT,
            required=True,
        ),
        StrInput(
            name="catalog",
            display_name="Catalog",
            info="Default catalog for unqualified table names (for example iceberg_data).",
        ),
        StrInput(
            name="schema_name",
            display_name="Schema",
            info="Default schema for unqualified table names.",
        ),
        DropdownInput(
            name="auth_mode",
            display_name="Authentication",
            options=AUTH_OPTIONS,
            value=AUTH_API_KEY,
            info=(
                "api_key: IBM Cloud IAM API key as the password for user ibmlhapikey (watsonx.data on IBM Cloud). "
                "basic: user name and password your watsonx.data instance expects (software / CPD)."
            ),
            real_time_refresh=True,
        ),
        StrInput(
            name="username",
            display_name="User Name",
            info=(
                "Presto user. For api_key authentication use ibmlhapikey (instance owner) or "
                "ibmlhapikey_<IBM Cloud account email> for a specific user."
            ),
            value=DEFAULT_API_KEY_USERNAME,
        ),
        SecretStrInput(
            name="api_key",
            display_name="IBM Cloud API Key",
            info="IBM Cloud IAM API key (api_key authentication).",
        ),
        SecretStrInput(
            name="password",
            display_name="Password",
            info="Password for basic authentication.",
            show=False,
        ),
        MultilineInput(
            name="query",
            display_name="SQL Query",
            info="Presto SQL to run, for example SELECT * FROM iceberg_data.sales.orders LIMIT 100.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_rows",
            display_name="Max Rows",
            info=f"Maximum rows returned (capped at {MAX_ROWS_CAP}).",
            value=DEFAULT_MAX_ROWS,
            range_spec={"min": 1, "max": MAX_ROWS_CAP, "step": 1},
            advanced=True,
        ),
        BoolInput(
            name="verify_ssl",
            display_name="Verify SSL Certificate",
            value=True,
            info="Disable only for development against a self-signed endpoint.",
            advanced=True,
        ),
        StrInput(
            name="ssl_ca_file",
            display_name="SSL CA Certificate",
            info="Path (or https URL) of the CA bundle for watsonx.data software instances. Leave empty on IBM Cloud.",
            advanced=True,
        ),
        IntInput(
            name="request_timeout",
            display_name="Request Timeout (seconds)",
            value=int(DEFAULT_REQUEST_TIMEOUT),
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result Table", name="result_table", method="run_query"),
    ]

    # ------------------------------------------------------------ build cfg
    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name == "auth_mode":
            basic = field_value == AUTH_BASIC
            if "password" in build_config:
                build_config["password"]["show"] = basic
            if "api_key" in build_config:
                build_config["api_key"]["show"] = not basic
            if "username" in build_config and not basic:
                current = build_config["username"].get("value") or ""
                if not current:
                    build_config["username"]["value"] = DEFAULT_API_KEY_USERNAME
        return build_config

    # ------------------------------------------------------------- helpers
    def _credentials(self) -> tuple[str, str]:
        mode = getattr(self, "auth_mode", AUTH_API_KEY) or AUTH_API_KEY
        username = (getattr(self, "username", "") or "").strip()
        if mode == AUTH_API_KEY:
            secret = (getattr(self, "api_key", "") or "").strip()
            username = username or DEFAULT_API_KEY_USERNAME
            if not secret:
                msg = "IBM Cloud API Key is required for api_key authentication."
                raise ValueError(msg)
            return username, secret
        secret = (getattr(self, "password", "") or "").strip()
        if not username or not secret:
            msg = "User Name and Password are required for basic authentication."
            raise ValueError(msg)
        return username, secret

    def _connection_kwargs(self) -> dict[str, Any]:
        host = validate_hostname(self.host)
        port = validate_port(getattr(self, "port", DEFAULT_PORT) or DEFAULT_PORT)
        # SSRF: the tenant controls host/port; gate them through the connector policy.
        validate_connector_url_for_ssrf(f"https://{host}:{port}")
        username, secret = self._credentials()
        kwargs: dict[str, Any] = {
            "host": host,
            "port": port,
            "user": username,
            "http_scheme": "https",
            "source": "langflow",
            "request_timeout": float(
                getattr(self, "request_timeout", DEFAULT_REQUEST_TIMEOUT) or DEFAULT_REQUEST_TIMEOUT
            ),
        }
        catalog = (getattr(self, "catalog", "") or "").strip()
        schema = (getattr(self, "schema_name", "") or "").strip()
        if catalog:
            kwargs["catalog"] = catalog
        if schema:
            kwargs["schema"] = schema
        kwargs["_password"] = secret
        return kwargs

    def _tls_verify(self) -> tuple[str | bool, str | None]:
        """Return the requests ``verify`` value plus any temporary CA file the caller must remove.

        An ``https://`` CA file is downloaded to a temporary path, so ownership of that file has
        to travel back to the caller. Discarding it leaks one file per query.
        """
        ca_file = (getattr(self, "ssl_ca_file", "") or "").strip()
        if ca_file:
            cert_path, is_temp, error = validate_and_prepare_ssl_certificate(
                ca_file, scope_ids=component_file_access_scopes(self)
            )
            if error or not cert_path:
                msg = f"Invalid SSL CA certificate: {error or 'unreadable file'}"
                raise ValueError(msg)
            return cert_path, (cert_path if is_temp else None)
        return bool(getattr(self, "verify_ssl", True)), None

    def _max_rows(self) -> int:
        rows = int(getattr(self, "max_rows", DEFAULT_MAX_ROWS) or DEFAULT_MAX_ROWS)
        return max(1, min(rows, MAX_ROWS_CAP))

    # ---------------------------------------------------------------- run
    def _run_sync(
        self, kwargs: dict[str, Any], query: str, max_rows: int, *, verify: str | bool
    ) -> list[dict[str, Any]]:
        try:
            from prestodb import dbapi
            from prestodb.auth import BasicAuthentication
        except ImportError as exc:  # pragma: no cover - guarded by the bundle's dependency list
            msg = "presto-python-client is not installed. Install the lfx-ibm bundle with its dependencies."
            raise ImportError(msg) from exc

        password = kwargs.pop("_password")
        connection = dbapi.connect(auth=BasicAuthentication(kwargs["user"], password), **kwargs)
        # prestodb builds its own requests.Session; TLS verification / CA bundle is set on it.
        connection._http_session.verify = verify  # noqa: SLF001 - documented prestodb pattern
        try:
            cursor = connection.cursor()
            cursor.execute(query)
            rows = cursor.fetchmany(max_rows)
            columns = _unique_columns([d[0] for d in (cursor.description or [])])
        finally:
            connection.close()
        return [dict(zip(columns, row, strict=False)) for row in rows]

    async def run_query(self) -> DataFrame:
        query = (self.query or "").strip()
        if not query:
            msg = "SQL Query is required."
            raise ValueError(msg)
        kwargs = self._connection_kwargs()
        verify, temp_cert_path = self._tls_verify()
        max_rows = self._max_rows()
        try:
            rows = await asyncio.to_thread(self._run_sync, kwargs, query, max_rows, verify=verify)
        except (ImportError, ValueError):
            raise
        except Exception as exc:
            msg = create_safe_error_message(exc, "watsonx.data Presto query failed")
            raise ValueError(msg) from exc
        finally:
            # ``_run_sync`` closes the connection before returning, so the downloaded CA file
            # is no longer needed on either the success or the failure path.
            if temp_cert_path:
                with contextlib.suppress(OSError):
                    Path(temp_cert_path).unlink(missing_ok=True)
        frame = DataFrame(rows)
        self.status = f"{len(frame)} row(s)"
        return frame
