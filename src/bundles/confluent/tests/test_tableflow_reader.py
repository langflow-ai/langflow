"""Unit tests for ``ConfluentTableflowReaderComponent`` (``lfx-confluent``).

``pyiceberg.catalog.load_catalog`` is patched with a fake catalog so the
tests cover REST-catalog property construction (credential, warehouse,
access delegation, BYOS storage keys), scan arguments (limit, filter,
projection, snapshot), table listing, and error handling without network.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_confluent import ConfluentTableflowReaderComponent
from lfx_confluent.components.confluent.tableflow_reader import BYOS_FIELDS

LOAD_CATALOG_TARGET = "pyiceberg.catalog.load_catalog"


class _FakeScan:
    def __init__(self, kwargs):
        self.kwargs = kwargs

    def to_pandas(self):
        return pd.DataFrame([{"id": 1, "status": "shipped"}, {"id": 2, "status": "shipped"}])


class _FakeTable:
    def __init__(self):
        self.scan_kwargs = None

    def scan(self, **kwargs):
        self.scan_kwargs = kwargs
        return _FakeScan(kwargs)


class _FakeCatalog:
    last: _FakeCatalog | None = None

    def __init__(self, name, **properties):
        self.name = name
        self.properties = properties
        self.loaded = None
        self.table = _FakeTable()
        _FakeCatalog.last = self

    def load_table(self, identifier):
        self.loaded = identifier
        return self.table

    def list_tables(self, namespace):
        return [(namespace, "orders"), (namespace, "payments")]


def _fake_load_catalog(name, **properties):
    return _FakeCatalog(name, **properties)


@pytest.fixture
def component() -> ConfluentTableflowReaderComponent:
    c = ConfluentTableflowReaderComponent()
    c.region = "us-east-1"
    c.organization_id = "org-1"
    c.environment_id = "env-abc"
    c.kafka_cluster_id = "lkc-xyz"
    c.api_key = "tf-key"  # pragma: allowlist secret
    c.api_secret = "tf-secret"  # noqa: S105  # pragma: allowlist secret
    c.table_name = "orders"
    c.row_filter = ""
    c.selected_fields = ""
    c.limit = 1000
    c.storage_mode = "confluent_managed"
    c.s3_access_key_id = ""
    c.s3_secret_access_key = ""
    c.s3_region = ""
    c.access_delegation = "vended-credentials"
    c.namespace = ""
    c.snapshot_id = ""
    c.catalog_uri_override = ""
    c.cloud = "aws"
    return c


def test_component_metadata():
    assert ConfluentTableflowReaderComponent.__name__ == "ConfluentTableflowReaderComponent"
    assert ConfluentTableflowReaderComponent.name == "ConfluentTableflowReader"


def test_catalog_properties_for_managed_storage(component):
    props = component.catalog_properties()
    assert props == {
        "type": "rest",
        "uri": "https://tableflow.us-east-1.aws.confluent.cloud/iceberg/catalog/organizations/org-1/environments/env-abc",
        "credential": "tf-key:tf-secret",  # pragma: allowlist secret
        "warehouse": "lkc-xyz",
        "header.X-Iceberg-Access-Delegation": "vended-credentials",
    }


def test_catalog_properties_for_byos_adds_s3_keys(component):
    component.storage_mode = "byos"
    component.access_delegation = "none"
    component.s3_access_key_id = "AKIA"  # pragma: allowlist secret
    component.s3_secret_access_key = "S3SECRET"  # noqa: S105  # pragma: allowlist secret
    component.s3_region = "us-east-1"
    props = component.catalog_properties()
    assert props["s3.access-key-id"] == "AKIA"
    assert props["s3.secret-access-key"] == "S3SECRET"  # pragma: allowlist secret
    assert props["s3.region"] == "us-east-1"
    assert "header.X-Iceberg-Access-Delegation" not in props


def test_catalog_properties_byos_requires_s3_credentials(component):
    component.storage_mode = "byos"
    with pytest.raises(ValueError, match="S3 access key ID"):
        component.catalog_properties()


def test_catalog_uri_override_is_ssrf_checked(component):
    component.catalog_uri_override = "https://tableflow.example.com/iceberg/catalog/x"
    assert component.catalog_uri() == "https://tableflow.example.com/iceberg/catalog/x"
    component.catalog_uri_override = "http://10.0.0.5/iceberg"
    with pytest.raises(SSRFProtectionError):
        component.catalog_uri()


def test_update_build_config_toggles_byos_fields(component):
    build_config = {k: {"show": False, "advanced": True} for k in BYOS_FIELDS}
    out = component.update_build_config(dict(build_config), "byos", field_name="storage_mode")
    assert all(out[k]["show"] for k in BYOS_FIELDS)
    out = component.update_build_config(dict(build_config), "confluent_managed", field_name="storage_mode")
    assert not any(out[k]["show"] for k in BYOS_FIELDS)


async def test_read_table_scans_with_filter_projection_limit_and_snapshot(component):
    component.row_filter = "status == 'shipped'"
    component.selected_fields = "id, status"
    component.limit = 50
    component.snapshot_id = "12345"
    with patch(LOAD_CATALOG_TARGET, side_effect=_fake_load_catalog):
        frame = await component.read_table()
    catalog = _FakeCatalog.last
    assert catalog.name == "tableflow"
    assert catalog.loaded == ("lkc-xyz", "orders")
    assert catalog.table.scan_kwargs == {
        "selected_fields": ("id", "status"),
        "limit": 50,
        "row_filter": "status == 'shipped'",
        "snapshot_id": 12345,
    }
    assert frame.to_dict(orient="records") == [{"id": 1, "status": "shipped"}, {"id": 2, "status": "shipped"}]


async def test_read_table_uses_namespace_override_and_default_projection(component):
    component.namespace = "custom_ns"
    with patch(LOAD_CATALOG_TARGET, side_effect=_fake_load_catalog):
        await component.read_table()
    assert _FakeCatalog.last.loaded == ("custom_ns", "orders")
    assert _FakeCatalog.last.table.scan_kwargs["selected_fields"] == ("*",)


async def test_read_table_keeps_dots_in_the_table_name(component):
    """A Tableflow table is named after its Kafka topic, and topics routinely contain dots.

    A string identifier would be split by PyIceberg into extra namespace levels.
    """
    component.table_name = "orders.v1"
    with patch(LOAD_CATALOG_TARGET, side_effect=_fake_load_catalog):
        await component.read_table()
    assert _FakeCatalog.last.loaded == ("lkc-xyz", "orders.v1")


async def test_read_table_requires_table_name(component):
    component.table_name = ""
    with pytest.raises(ValueError, match="Table \\(Topic\\) is required"):
        await component.read_table()


async def test_read_table_rejects_non_integer_snapshot(component):
    component.snapshot_id = "abc"
    with patch(LOAD_CATALOG_TARGET, side_effect=_fake_load_catalog), pytest.raises(ValueError, match="Snapshot ID"):
        await component.read_table()


async def test_read_table_wraps_catalog_errors(component):
    def _boom(_name, **_properties):
        msg = "catalog unreachable"
        raise RuntimeError(msg)

    with patch(LOAD_CATALOG_TARGET, side_effect=_boom), pytest.raises(ValueError, match="Tableflow read failed"):
        await component.read_table()


async def test_list_tables_returns_namespace_and_tables(component):
    with patch(LOAD_CATALOG_TARGET, side_effect=_fake_load_catalog):
        data = await component.list_tables()
    assert data.data["namespace"] == "lkc-xyz"
    assert data.data["tables"] == [
        {"namespace": "lkc-xyz", "table": "orders"},
        {"namespace": "lkc-xyz", "table": "payments"},
    ]


def test_limit_is_clamped(component):
    component.limit = 10_000_000
    assert component._limit() == 100_000
    component.limit = 0
    assert component._limit() == 1  # an explicit zero clamps to the minimum, not the default
    component.limit = None
    assert component._limit() == 1000  # only a missing value falls back to the default


def test_selected_fields_parsing(component):
    component.selected_fields = " a , b ,,"
    assert component._selected_fields() == ("a", "b")
