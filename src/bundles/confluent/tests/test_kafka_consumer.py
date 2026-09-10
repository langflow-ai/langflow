"""Unit tests for ``ConfluentKafkaConsumerComponent`` (``lfx-confluent``).

``confluent_kafka.Consumer`` is patched with a fake that hands out scripted
messages, so the tests cover the bounded consume loop, value decoding, row
shape, offset commit, and close-on-error without a broker.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_confluent import ConfluentKafkaConsumerComponent
from lfx_confluent.components.confluent.kafka_consumer import SCHEMA_REGISTRY_FORMATS

CONSUMER_TARGET = "confluent_kafka.Consumer"


class _FakeMessage:
    def __init__(self, value, key=b"k", topic="orders", partition=0, offset=0, headers=None, error=None):
        self._value, self._key, self._topic = value, key, topic
        self._partition, self._offset, self._headers, self._error = partition, offset, headers, error

    def error(self):
        return self._error

    def value(self):
        return self._value

    def key(self):
        return self._key

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset

    def timestamp(self):
        return (1, 1_700_000_000_000 + self._offset)

    def headers(self):
        return self._headers


class _FakeConsumer:
    instances: list[_FakeConsumer] = []
    script: list[list[_FakeMessage]] = []

    def __init__(self, config):
        self.config = config
        self.subscribed = None
        self.closed = False
        self.committed = False
        self.consume_calls = 0
        _FakeConsumer.instances.append(self)

    def subscribe(self, topics):
        self.subscribed = topics

    def consume(self, num_messages, timeout):  # noqa: ARG002 - mirrors the confluent_kafka signature
        self.consume_calls += 1
        if _FakeConsumer.script:
            batch = _FakeConsumer.script.pop(0)
            return batch[:num_messages]
        return []

    def commit(self, *, asynchronous=True):  # noqa: ARG002 - mirrors the confluent_kafka signature
        self.committed = True

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_fake():
    _FakeConsumer.instances.clear()
    _FakeConsumer.script = []
    yield
    _FakeConsumer.instances.clear()
    _FakeConsumer.script = []


@pytest.fixture
def component() -> ConfluentKafkaConsumerComponent:
    c = ConfluentKafkaConsumerComponent()
    c.bootstrap_servers = "pkc-1.us-east-1.aws.confluent.cloud:9092"
    c.api_key = "key"  # pragma: allowlist secret
    c.api_secret = "secret"  # noqa: S105  # pragma: allowlist secret
    c.topics = "orders, payments"
    c.group_id = "test-group"
    c.max_messages = 3
    c.timeout_seconds = 2.0
    c.auto_offset_reset = "earliest"
    c.commit_offsets = True
    c.value_format = "json"
    c.schema_registry_url = ""
    c.schema_registry_key = ""
    c.schema_registry_secret = ""
    c.client_config = {}
    return c


def test_component_metadata():
    assert ConfluentKafkaConsumerComponent.__name__ == "ConfluentKafkaConsumerComponent"
    assert ConfluentKafkaConsumerComponent.name == "ConfluentKafkaConsumer"


def test_update_build_config_shows_registry_fields_for_schema_formats(component):
    fields = ("schema_registry_url", "schema_registry_key", "schema_registry_secret")
    build_config = {k: {"show": False, "advanced": True} for k in fields}
    for fmt in SCHEMA_REGISTRY_FORMATS:
        out = component.update_build_config(dict(build_config), fmt, field_name="value_format")
        assert all(out[k]["show"] for k in build_config)
    out = component.update_build_config(dict(build_config), "json", field_name="value_format")
    assert not any(out[k]["show"] for k in build_config)


def test_bounds_are_clamped(component):
    component.max_messages = 999_999
    component.timeout_seconds = 9_999
    assert component._bounds() == (10_000, 300.0)


def test_group_id_defaults_when_empty(component):
    component.group_id = ""
    assert component._resolved_group_id().startswith("langflow")


async def test_consume_reads_bounded_batch_and_promotes_json_fields(component):
    _FakeConsumer.script = [
        [
            _FakeMessage(json.dumps({"id": 1, "amount": 10}).encode(), offset=0, headers=[("h", b"v")]),
            _FakeMessage(json.dumps({"id": 2, "amount": 20}).encode(), offset=1),
        ],
        [
            _FakeMessage(b"not-json", offset=2),
            _FakeMessage(b"never-read", offset=3),
        ],
    ]
    with patch(CONSUMER_TARGET, _FakeConsumer):
        frame = await component.consume()
    consumer = _FakeConsumer.instances[0]
    assert consumer.subscribed == ["orders", "payments"]
    assert consumer.config["group.id"] == "test-group"
    assert consumer.config["auto.offset.reset"] == "earliest"
    assert consumer.config["enable.auto.commit"] is False
    assert consumer.config["security.protocol"] == "SASL_SSL"
    assert consumer.committed is True
    assert consumer.closed is True
    rows = frame.to_dict(orient="records")
    assert len(rows) == 3
    assert rows[0]["id"] == 1
    assert rows[0]["amount"] == 10
    assert rows[0]["value"] == {"id": 1, "amount": 10}
    assert rows[0]["headers"] == {"h": "v"}
    assert rows[0]["key"] == "k"
    assert rows[2]["value"] == "not-json"


async def test_consume_string_format_returns_text(component):
    component.value_format = "string"
    _FakeConsumer.script = [[_FakeMessage(b'{"id": 1}')]]
    with patch(CONSUMER_TARGET, _FakeConsumer):
        frame = await component.consume()
    assert frame.to_dict(orient="records")[0]["value"] == '{"id": 1}'


async def test_consume_returns_empty_frame_on_timeout(component):
    component.timeout_seconds = 0.5
    with patch(CONSUMER_TARGET, _FakeConsumer):
        frame = await component.consume()
    assert len(frame) == 0
    assert _FakeConsumer.instances[0].closed is True
    assert _FakeConsumer.instances[0].committed is False


async def test_consume_closes_consumer_on_kafka_error(component):
    from confluent_kafka import KafkaError

    class _Err:
        def code(self):
            return KafkaError._UNKNOWN_TOPIC

        def __str__(self):
            return "unknown topic"

    _FakeConsumer.script = [[_FakeMessage(b"{}", error=_Err())]]
    with patch(CONSUMER_TARGET, _FakeConsumer), pytest.raises(ValueError, match="Kafka consume failed"):
        await component.consume()
    assert _FakeConsumer.instances[0].closed is True


async def test_consume_skips_partition_eof(component):
    from confluent_kafka import KafkaError

    class _Eof:
        def code(self):
            return KafkaError._PARTITION_EOF

    _FakeConsumer.script = [[_FakeMessage(b"{}", error=_Eof()), _FakeMessage(json.dumps({"id": 9}).encode())]]
    component.max_messages = 2
    component.timeout_seconds = 0.5
    with patch(CONSUMER_TARGET, _FakeConsumer):
        frame = await component.consume()
    rows = frame.to_dict(orient="records")
    assert len(rows) == 1  # the EOF sentinel is skipped, not surfaced as a row
    assert rows[0]["id"] == 9


async def test_consume_blocks_ssrf_bootstrap_host(component):
    component.bootstrap_servers = "10.0.0.5:9092"
    with pytest.raises(SSRFProtectionError):
        await component.consume()


async def test_consume_requires_topics(component):
    component.topics = " , "
    with pytest.raises(ValueError, match="At least one topic"):
        await component.consume()


def test_registry_deserializer_requires_registry_url(component):
    component.value_format = "avro"
    with pytest.raises(ValueError, match="endpoint URL is required"):
        component._value_deserializer()
