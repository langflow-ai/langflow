from __future__ import annotations

from typing import Any

import oracledb
from langchain_oracledb.document_loaders import OracleAutonomousDatabaseLoader, OracleDocLoader

from lfx.custom.custom_component.component import Component
from lfx.io import DictInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from .connection import build_connection_params, split_credentialized_dsn


class OracleDocLoaderComponent(Component):
    display_name = "Oracle Doc Loader"
    description = "Read documents from Oracle Database using OracleDocLoader."
    documentation = "https://docs.langchain.com/oss/python/integrations/document_loaders/oracleai"
    trace_type = "tool"
    icon = "Oracle"
    name = "OracleDocLoader"

    inputs = [
        SecretStrInput(name="user", display_name="User", required=False),
        SecretStrInput(name="password", display_name="Password", required=False),
        SecretStrInput(name="dsn", display_name="DSN", required=True),
        SecretStrInput(name="wallet_password", display_name="Wallet Password", required=False, advanced=True),
        DictInput(
            name="connection_params",
            display_name="Additional Connection Parameters",
            info="Non-secret arguments passed to python-oracledb connect(), such as config_dir and wallet_location.",
            required=False,
            advanced=True,
        ),
        DictInput(
            name="params",
            display_name="Loader Parameters",
            info="Arguments passed to langchain-oracledb OracleDocLoader.",
            required=True,
        ),
    ]

    outputs = [
        Output(name="data", display_name="JSON", method="load_documents"),
    ]

    def load_documents(self) -> list[Data]:
        connection_params = build_connection_params(
            self.connection_params,
            user=self.user,
            password=self.password,
            dsn=self.dsn,
            wallet_password=self.wallet_password,
        )
        with oracledb.connect(**connection_params) as connection:
            loader = OracleDocLoader(connection, self.params)
            data = [Data.from_document(doc) for doc in loader.load()]

        self.status = data
        return data


class OracleAutonomousDatabaseLoaderComponent(Component):
    display_name = "Oracle Autonomous Database Loader"
    description = "Load rows from Oracle Autonomous Database as documents."
    documentation = (
        "https://github.com/oracle/langchain-oracle/blob/main/libs/oracledb/"
        "langchain_oracledb/document_loaders/oracleadb_loader.py"
    )
    trace_type = "tool"
    icon = "Oracle"
    name = "OracleAutonomousDatabaseLoader"

    inputs = [
        StrInput(
            name="query",
            display_name="SQL Query",
            required=True,
            info="SQL query to execute. Each row becomes a document.",
        ),
        SecretStrInput(name="user", display_name="User", required=False),
        SecretStrInput(name="password", display_name="Password", required=False),
        SecretStrInput(name="dsn", display_name="DSN", required=True),
        SecretStrInput(name="wallet_password", display_name="Wallet Password", required=False, advanced=True),
        DictInput(
            name="connection_params",
            display_name="Additional Connection Parameters",
            info="Non-secret Oracle options such as schema, config_dir, and wallet_location.",
            required=False,
            advanced=True,
        ),
        MultilineInput(
            name="metadata",
            display_name="Metadata Columns",
            required=False,
            advanced=True,
            info="Comma-separated list of result columns to copy into document metadata.",
        ),
        DictInput(
            name="parameter",
            display_name="Bind Parameters",
            required=False,
            advanced=True,
            info="Bind variables for the SQL query.",
        ),
    ]

    outputs = [
        Output(name="data", display_name="JSON", method="load_documents"),
    ]

    def build_template_config(self) -> dict[str, Any]:
        """Build template config from this class to avoid cross-class metadata bleed."""
        return self.get_template_config(self)

    def _parse_metadata(self) -> list[str] | None:
        metadata = getattr(self, "metadata", None)
        if metadata is None:
            return None
        if isinstance(metadata, str):
            values = [column.strip() for column in metadata.split(",") if column.strip()]
            return values or None
        if isinstance(metadata, list):
            return metadata or None
        return None

    def _parse_connection_params(self) -> dict[str, Any]:
        connection_params = build_connection_params(
            self.connection_params,
            user=self.user,
            password=self.password,
            dsn=self.dsn,
            wallet_password=self.wallet_password,
        )
        dsn = connection_params.get("dsn") or connection_params.get("connection_string") or connection_params.get("tns")

        user = connection_params.get("user") or connection_params.get("username")
        password = connection_params.get("password")

        if isinstance(dsn, str) and (not user or not password):
            parsed_user, parsed_password, parsed_dsn = split_credentialized_dsn(dsn)
            user = user or parsed_user
            password = password or parsed_password
            dsn = parsed_dsn

        if not user or not password:
            msg = (
                "Connection settings must include user and password, either in the dedicated fields or inside the DSN."
            )
            raise ValueError(msg)

        return {
            "user": user,
            "password": password,
            "dsn": dsn,
            "schema": connection_params.get("schema"),
            "config_dir": connection_params.get("config_dir"),
            "wallet_location": connection_params.get("wallet_location"),
            "wallet_password": connection_params.get("wallet_password"),
        }

    def _parse_parameter(self) -> Any:
        parameter = getattr(self, "parameter", None)
        return parameter or None

    def load_documents(self) -> list[Data]:
        loader = OracleAutonomousDatabaseLoader(
            query=self.query,
            metadata=self._parse_metadata(),
            parameter=self._parse_parameter(),
            **self._parse_connection_params(),
        )

        data = [Data.from_document(doc) for doc in loader.load()]
        self.status = data
        return data
