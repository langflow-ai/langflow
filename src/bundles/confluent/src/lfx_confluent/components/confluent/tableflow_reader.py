"""Read Confluent Tableflow tables (Kafka topics materialized as Apache Iceberg) into a DataFrame."""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx_confluent.components.confluent._common import (
    DEFAULT_CLOUD,
    DEFAULT_REGION,
    ensure_url_allowed,
    require_token,
    tableflow_catalog_url,
)

STORAGE_CONFLUENT_MANAGED = "confluent_managed"
STORAGE_BYOS = "byos"
STORAGE_OPTIONS = [STORAGE_CONFLUENT_MANAGED, STORAGE_BYOS]

DELEGATION_VENDED = "vended-credentials"
DELEGATION_REMOTE_SIGNING = "remote-signing"
DELEGATION_NONE = "none"
DELEGATION_OPTIONS = [DELEGATION_VENDED, DELEGATION_REMOTE_SIGNING, DELEGATION_NONE]

DEFAULT_LIMIT = 1000
MAX_LIMIT = 100_000
BYOS_FIELDS = ("s3_access_key_id", "s3_secret_access_key", "s3_region")


class ConfluentTableflowReaderComponent(Component):
    """Query a Tableflow-materialized Iceberg table through the Tableflow REST catalog.

    Tableflow turns a Kafka topic into an Apache Iceberg table and serves it
    through a standards-based Iceberg REST catalog.  This component reads that
    table with ``pyiceberg`` (no JVM), applying an optional row filter, column
    projection, and a hard row limit, and returns the result as a DataFrame.
    Tableflow tables are read-only from external engines: to change the data,
    publish to the source topic.
    """

    display_name = "Confluent Tableflow Reader"
    description = (
        "Read a Kafka topic that Tableflow has materialized as an Apache Iceberg table (via the "
        "Tableflow Iceberg REST catalog) into a DataFrame, with a row filter, projection, and limit."
    )
    documentation: str = "https://docs.langflow.org/bundles-confluent"
    icon = "Confluent"
    name = "ConfluentTableflowReader"
    metadata = {"keywords": ["confluent", "tableflow", "iceberg", "kafka", "lakehouse", "streamhouse", "ibm"]}

    inputs = [
        StrInput(
            name="region",
            display_name="Cloud Region",
            info="Confluent Cloud region of the Kafka cluster (for example us-east-1).",
            value=DEFAULT_REGION,
            required=True,
        ),
        StrInput(
            name="organization_id",
            display_name="Organization ID",
            info="Confluent Cloud organization ID.",
            required=True,
        ),
        StrInput(
            name="environment_id",
            display_name="Environment ID",
            info="Confluent Cloud environment ID (for example env-abc123).",
            required=True,
        ),
        StrInput(
            name="kafka_cluster_id",
            display_name="Kafka Cluster ID",
            info=(
                "Kafka cluster ID (for example lkc-abc123). Tableflow exposes it as the Iceberg warehouse "
                "and namespace."
            ),
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Tableflow API Key",
            info="Tableflow API key (Iceberg REST catalog credential).",
            required=True,
        ),
        SecretStrInput(
            name="api_secret",
            display_name="Tableflow API Secret",
            info="Secret paired with the Tableflow API key.",
            required=True,
        ),
        MessageTextInput(
            name="table_name",
            display_name="Table (Topic)",
            info="Tableflow table name -- the Kafka topic name. Leave empty and use the Tables output to list them.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="row_filter",
            display_name="Row Filter",
            info="Optional Iceberg row filter expression, for example status == 'shipped' AND amount > 10.",
            tool_mode=True,
        ),
        StrInput(
            name="selected_fields",
            display_name="Columns",
            info="Optional comma-separated list of columns to return. Empty returns every column.",
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Row Limit",
            info=f"Maximum rows to return (capped at {MAX_LIMIT}).",
            value=DEFAULT_LIMIT,
            range_spec={"min": 1, "max": MAX_LIMIT, "step": 1},
            tool_mode=True,
        ),
        DropdownInput(
            name="storage_mode",
            display_name="Storage",
            options=STORAGE_OPTIONS,
            value=STORAGE_CONFLUENT_MANAGED,
            info=(
                "confluent_managed: Confluent-provisioned storage (credentials vended by the catalog). "
                "byos: your own S3 bucket (provide the S3 fields)."
            ),
            real_time_refresh=True,
            advanced=True,
        ),
        SecretStrInput(name="s3_access_key_id", display_name="S3 Access Key ID", advanced=True, show=False),
        SecretStrInput(name="s3_secret_access_key", display_name="S3 Secret Access Key", advanced=True, show=False),
        StrInput(name="s3_region", display_name="S3 Region", advanced=True, show=False),
        DropdownInput(
            name="access_delegation",
            display_name="Access Delegation",
            options=DELEGATION_OPTIONS,
            value=DELEGATION_VENDED,
            info=(
                "Iceberg REST access-delegation mode requested from the catalog. Leave the default unless "
                "Confluent documents otherwise for your setup."
            ),
            advanced=True,
        ),
        StrInput(
            name="namespace",
            display_name="Namespace Override",
            info="Iceberg namespace holding the table. Defaults to the Kafka cluster ID.",
            advanced=True,
        ),
        StrInput(
            name="snapshot_id",
            display_name="Snapshot ID",
            info="Optional Iceberg snapshot ID to read a specific point in time.",
            advanced=True,
        ),
        StrInput(
            name="catalog_uri_override",
            display_name="Catalog URI Override",
            info="Full Iceberg REST catalog URI. Leave empty to build it from the region and IDs.",
            advanced=True,
        ),
        StrInput(
            name="cloud",
            display_name="Cloud Provider",
            info="Cloud provider segment of the catalog host (aws, gcp, azure).",
            value=DEFAULT_CLOUD,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result Table", name="result_table", method="read_table"),
        Output(display_name="Tables", name="tables", method="list_tables"),
    ]

    # ------------------------------------------------------------ build cfg
    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name == "storage_mode":
            byos = field_value == STORAGE_BYOS
            for key in BYOS_FIELDS:
                if key in build_config:
                    build_config[key]["show"] = byos
                    build_config[key]["advanced"] = not byos
        return build_config

    # ------------------------------------------------------------- helpers
    def catalog_uri(self) -> str:
        override = (getattr(self, "catalog_uri_override", "") or "").strip()
        if override:
            return ensure_url_allowed(override)
        uri = tableflow_catalog_url(
            self.region,
            self.organization_id,
            self.environment_id,
            cloud=getattr(self, "cloud", DEFAULT_CLOUD) or DEFAULT_CLOUD,
        )
        return ensure_url_allowed(uri)

    def catalog_properties(self) -> dict[str, str]:
        """Build the pyiceberg REST catalog properties for Tableflow."""
        key = (self.api_key or "").strip()
        secret = (self.api_secret or "").strip()
        if not key or not secret:
            msg = "Both the Tableflow API key and the API secret are required."
            raise ValueError(msg)
        cluster = require_token(self.kafka_cluster_id, "Kafka cluster ID")
        props: dict[str, str] = {
            "type": "rest",
            "uri": self.catalog_uri(),
            "credential": f"{key}:{secret}",
            "warehouse": cluster,
        }
        delegation = getattr(self, "access_delegation", DELEGATION_VENDED) or DELEGATION_VENDED
        if delegation != DELEGATION_NONE:
            props["header.X-Iceberg-Access-Delegation"] = delegation
        if (getattr(self, "storage_mode", STORAGE_CONFLUENT_MANAGED) or STORAGE_CONFLUENT_MANAGED) == STORAGE_BYOS:
            access_key = (getattr(self, "s3_access_key_id", "") or "").strip()
            secret_key = (getattr(self, "s3_secret_access_key", "") or "").strip()
            s3_region = (getattr(self, "s3_region", "") or "").strip()
            if not access_key or not secret_key:
                msg = "S3 access key ID and secret access key are required for bring-your-own-storage."
                raise ValueError(msg)
            props["s3.access-key-id"] = access_key
            props["s3.secret-access-key"] = secret_key
            if s3_region:
                props["s3.region"] = s3_region
        return props

    def _namespace(self) -> str:
        override = (getattr(self, "namespace", "") or "").strip()
        return override or require_token(self.kafka_cluster_id, "Kafka cluster ID")

    def _selected_fields(self) -> tuple[str, ...]:
        raw = (getattr(self, "selected_fields", "") or "").strip()
        if not raw:
            return ("*",)
        fields = tuple(f.strip() for f in raw.split(",") if f.strip())
        return fields or ("*",)

    def _limit(self) -> int:
        # Only a missing / blank limit falls back to the default: an explicit 0 from a tool
        # or API caller means "as few as possible", not "give me DEFAULT_LIMIT rows".
        raw = getattr(self, "limit", None)
        limit = DEFAULT_LIMIT if raw is None or raw == "" else int(raw)
        return max(1, min(limit, MAX_LIMIT))

    @staticmethod
    def _load_catalog(properties: dict[str, str]):
        try:
            from pyiceberg.catalog import load_catalog
        except ImportError as exc:  # pragma: no cover - exercised on platforms without pyiceberg
            msg = "pyiceberg is not installed. Install the lfx-confluent bundle with its dependencies."
            raise ImportError(msg) from exc
        return load_catalog("tableflow", **properties)

    # --------------------------------------------------------------- reads
    def _read_sync(self, properties: dict[str, str], namespace: str, table: str) -> Any:
        catalog = self._load_catalog(properties)
        # Tuple identifier, not "<namespace>.<table>": PyIceberg splits a string identifier
        # on ".", and a Tableflow table is named after its Kafka topic, which routinely
        # contains dots ("orders.v1").
        iceberg_table = catalog.load_table((*namespace.split("."), table))
        scan_kwargs: dict[str, Any] = {"selected_fields": self._selected_fields(), "limit": self._limit()}
        row_filter = (getattr(self, "row_filter", "") or "").strip()
        if row_filter:
            scan_kwargs["row_filter"] = row_filter
        snapshot_id = (getattr(self, "snapshot_id", "") or "").strip()
        if snapshot_id:
            try:
                scan_kwargs["snapshot_id"] = int(snapshot_id)
            except ValueError as exc:
                msg = f"Snapshot ID must be an integer, got {snapshot_id!r}."
                raise ValueError(msg) from exc
        return iceberg_table.scan(**scan_kwargs).to_pandas()

    def _list_sync(self, properties: dict[str, str], namespace: str) -> list[dict[str, str]]:
        catalog = self._load_catalog(properties)
        identifiers = catalog.list_tables(namespace)
        rows: list[dict[str, str]] = []
        for identifier in identifiers:
            parts = tuple(identifier) if isinstance(identifier, tuple | list) else (namespace, str(identifier))
            rows.append({"namespace": ".".join(parts[:-1]), "table": parts[-1]})
        return rows

    async def read_table(self) -> DataFrame:
        table = (getattr(self, "table_name", "") or "").strip()
        if not table:
            msg = "Table (Topic) is required to read rows. Use the Tables output to list available tables."
            raise ValueError(msg)
        properties = self.catalog_properties()
        namespace = self._namespace()
        try:
            pandas_frame = await asyncio.to_thread(self._read_sync, properties, namespace, table)
        except ImportError:
            raise
        except ValueError:
            raise
        except Exception as exc:
            msg = f"Tableflow read failed for {namespace}.{table}: {exc}"
            raise ValueError(msg) from exc
        frame = DataFrame(pandas_frame)
        self.status = f"Read {len(frame)} row(s) from {namespace}.{table}"
        return frame

    async def list_tables(self) -> Data:
        properties = self.catalog_properties()
        namespace = self._namespace()
        try:
            rows = await asyncio.to_thread(self._list_sync, properties, namespace)
        except ImportError:
            raise
        except ValueError:
            raise
        except Exception as exc:
            msg = f"Tableflow catalog listing failed for namespace {namespace}: {exc}"
            raise ValueError(msg) from exc
        self.status = f"{len(rows)} table(s) in {namespace}"
        return Data(data={"namespace": namespace, "tables": rows})
