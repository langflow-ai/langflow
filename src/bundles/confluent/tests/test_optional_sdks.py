"""Regression: the Confluent bundle must import without ``confluent_kafka`` / ``pyiceberg``.

Both SDKs are imported lazily (inside the build methods) so the bundle still
loads -- and the MCP preset component still works -- on a platform where a
wheel is unavailable.  These tests *simulate* the packages' absence (a
``None`` entry in ``sys.modules`` makes the import raise ``ImportError``) so
they run on every platform, and guard against re-introducing a module-level
import of either SDK.
"""

from __future__ import annotations

import importlib
import sys

import pytest

_SIMULATED_MISSING = ("confluent_kafka", "pyiceberg", "pyiceberg.catalog")


def _bundle_module_names() -> list[str]:
    return [name for name in sys.modules if name == "lfx_confluent" or name.startswith("lfx_confluent.")]


@pytest.fixture
def without_sdks():
    saved = {name: sys.modules[name] for name in _bundle_module_names()}
    for name in saved:
        del sys.modules[name]
    sdk_roots = {"confluent_kafka", "pyiceberg"}
    saved_sdks = {name: sys.modules.pop(name, None) for name in list(sys.modules) if name.split(".")[0] in sdk_roots}
    for name in _SIMULATED_MISSING:
        sys.modules[name] = None
    try:
        yield
    finally:
        for name in _SIMULATED_MISSING:
            sys.modules.pop(name, None)
        for name in _bundle_module_names():
            del sys.modules[name]
        sys.modules.update({k: v for k, v in saved_sdks.items() if v is not None})
        sys.modules.update(saved)


@pytest.mark.usefixtures("without_sdks")
def test_bundle_imports_without_sdks():
    module = importlib.import_module("lfx_confluent")
    assert {
        "ConfluentContextEngineComponent",
        "ConfluentKafkaConsumerComponent",
        "ConfluentKafkaProducerComponent",
        "ConfluentTableflowReaderComponent",
    } <= set(module.__all__)


@pytest.mark.usefixtures("without_sdks")
async def test_producer_raises_clear_error_without_confluent_kafka():
    from lfx.schema.message import Message

    module = importlib.import_module("lfx_confluent.components.confluent.kafka_producer")
    c = module.ConfluentKafkaProducerComponent()
    c.bootstrap_servers = "pkc-1.us-east-1.aws.confluent.cloud:9092"
    c.api_key = c.api_secret = ""
    c.topic = "t"
    c.message = Message(text="x")
    c.headers = {}
    c.client_config = {}
    c.flush_timeout = 1
    with pytest.raises(ImportError, match="confluent-kafka is not installed"):
        await c.produce()


@pytest.mark.usefixtures("without_sdks")
async def test_tableflow_raises_clear_error_without_pyiceberg():
    module = importlib.import_module("lfx_confluent.components.confluent.tableflow_reader")
    c = module.ConfluentTableflowReaderComponent()
    c.region, c.organization_id, c.environment_id, c.kafka_cluster_id = "us-east-1", "org", "env-1", "lkc-1"
    c.api_key, c.api_secret = "k", "s"  # pragma: allowlist secret
    c.table_name = "orders"
    c.storage_mode = "confluent_managed"
    c.access_delegation = "vended-credentials"
    c.catalog_uri_override = c.namespace = c.snapshot_id = c.row_filter = c.selected_fields = ""
    c.limit = 10
    with pytest.raises(ImportError, match="pyiceberg is not installed"):
        await c.read_table()
