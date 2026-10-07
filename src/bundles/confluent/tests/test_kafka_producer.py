"""Unit tests for ``ConfluentKafkaProducerComponent`` (``lfx-confluent``).

``confluent_kafka.Producer`` is patched with a fake that invokes delivery
callbacks synchronously, so the tests exercise payload encoding, header
handling, and delivery-report aggregation without a broker.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_confluent import ConfluentKafkaProducerComponent

PRODUCER_TARGET = "confluent_kafka.Producer"


class _FakeMessage:
    def __init__(self, topic, key, partition=0, offset=7):
        self._topic, self._key, self._partition, self._offset = topic, key, partition, offset

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset

    def timestamp(self):
        return (1, 1_700_000_000_000)

    def key(self):
        return self._key


class _FakeProducer:
    instances: list[_FakeProducer] = []

    def __init__(self, config):
        self.config = config
        self.produced: list[dict] = []
        self.flushed_with = None
        self.remaining_after_flush = 0
        self.fail_every = None
        _FakeProducer.instances.append(self)

    def produce(self, topic, value=None, key=None, headers=None, on_delivery=None):
        self.produced.append({"topic": topic, "value": value, "key": key, "headers": headers})
        if self.fail_every and len(self.produced) % self.fail_every == 0:
            on_delivery(RuntimeError("broker said no"), None)
        else:
            on_delivery(None, _FakeMessage(topic, key, offset=len(self.produced)))

    def poll(self, _timeout):
        return 0

    def flush(self, timeout):
        self.flushed_with = timeout
        return self.remaining_after_flush


@pytest.fixture(autouse=True)
def _reset_fake():
    _FakeProducer.instances.clear()
    yield
    _FakeProducer.instances.clear()


@pytest.fixture
def component() -> ConfluentKafkaProducerComponent:
    c = ConfluentKafkaProducerComponent()
    c.bootstrap_servers = "pkc-1.us-east-1.aws.confluent.cloud:9092"
    c.api_key = "key"  # pragma: allowlist secret
    c.api_secret = "secret"  # noqa: S105  # pragma: allowlist secret
    c.topic = "orders"
    c.key = ""
    c.serialization = "json"
    c.headers = {}
    c.flush_timeout = 10
    c.client_config = {}
    return c


def test_component_metadata():
    assert ConfluentKafkaProducerComponent.__name__ == "ConfluentKafkaProducerComponent"
    assert ConfluentKafkaProducerComponent.name == "ConfluentKafkaProducer"


def test_records_from_message_data_and_dataframe(component):
    component.message = Message(text="hello")
    assert component._records() == [{"key": None, "value": b"hello"}]

    component.message = Data(data={"a": 1})
    assert json.loads(component._records()[0]["value"]) == {"a": 1}

    component.key = "k1"
    component.message = DataFrame([{"a": 1}, {"a": 2}])
    records = component._records()
    assert [json.loads(r["value"]) for r in records] == [{"a": 1}, {"a": 2}]
    assert all(r["key"] == "k1" for r in records)


def test_records_require_a_payload(component):
    component.message = None
    with pytest.raises(ValueError, match="Connect a Message"):
        component._records()


def test_record_headers_from_dict_and_list(component):
    component.headers = {"source": "langflow"}
    assert component._record_headers() == [("source", b"langflow")]
    component.headers = [{"a": "1"}, {"b": "2"}]
    assert component._record_headers() == [("a", b"1"), ("b", b"2")]
    component.headers = {}
    assert component._record_headers() is None


async def test_produce_publishes_each_row_and_reports_delivery(component):
    component.message = DataFrame([{"id": 1}, {"id": 2}, {"id": 3}])
    component.headers = {"source": "langflow"}
    component.client_config = {"acks": "all"}
    with patch(PRODUCER_TARGET, _FakeProducer):
        result = await component.produce()
    producer = _FakeProducer.instances[0]
    assert producer.config["bootstrap.servers"] == "pkc-1.us-east-1.aws.confluent.cloud:9092"
    assert producer.config["security.protocol"] == "SASL_SSL"
    assert producer.config["sasl.username"] == "key"
    assert producer.config["acks"] == "all"
    assert len(producer.produced) == 3
    assert producer.produced[0]["headers"] == [("source", b"langflow")]
    assert producer.flushed_with == 10.0
    assert result.data["records_sent"] == 3
    assert result.data["delivered"] == 3
    assert result.data["failed"] == 0
    assert result.data["reports"][0]["offset"] == 1


@pytest.mark.parametrize(
    ("configured", "expected"),
    [(-1, 1.0), (0, 10.0), (0.2, 1.0), (10, 10.0), (10_000, 300.0)],
)
async def test_flush_timeout_is_clamped(component, configured, expected):
    """A negative timeout would make ``Producer.flush`` block forever and pin the worker."""
    component.message = DataFrame([{"id": 1}])
    component.flush_timeout = configured
    with patch(PRODUCER_TARGET, _FakeProducer):
        await component.produce()
    assert _FakeProducer.instances[-1].flushed_with == expected


async def test_produce_reports_partial_failures(component):
    component.message = DataFrame([{"id": 1}, {"id": 2}])

    class _Flaky(_FakeProducer):
        def __init__(self, config):
            super().__init__(config)
            self.fail_every = 2

    with patch(PRODUCER_TARGET, _Flaky):
        result = await component.produce()
    assert result.data["delivered"] == 1
    assert result.data["failed"] == 1
    assert any(not r["delivered"] for r in result.data["reports"])


async def test_produce_raises_when_nothing_delivered(component):
    component.message = Message(text="x")

    class _Broken(_FakeProducer):
        def __init__(self, config):
            super().__init__(config)
            self.fail_every = 1

    with patch(PRODUCER_TARGET, _Broken), pytest.raises(ValueError, match="No records were delivered"):
        await component.produce()


async def test_produce_flags_unacknowledged_records(component):
    component.message = Message(text="x")

    class _Slow(_FakeProducer):
        def __init__(self, config):
            super().__init__(config)
            self.remaining_after_flush = 1

    with patch(PRODUCER_TARGET, _Slow):
        result = await component.produce()
    assert result.data["failed"] == 1
    assert "not acknowledged" in result.data["reports"][-1]["error"]


async def test_produce_blocks_ssrf_bootstrap_host(component):
    component.message = Message(text="x")
    component.bootstrap_servers = "169.254.169.254:9092"
    with pytest.raises(SSRFProtectionError):
        await component.produce()


async def test_produce_requires_topic(component):
    component.message = Message(text="x")
    component.topic = "  "
    with pytest.raises(ValueError, match="Topic is required"):
        await component.produce()
