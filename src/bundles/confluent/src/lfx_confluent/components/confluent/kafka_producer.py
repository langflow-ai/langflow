"""Publish flow results to a Kafka topic on Confluent Cloud / Platform."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DictInput, DropdownInput, HandleInput, IntInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx_confluent.components.confluent._common import kafka_client_config, validate_bootstrap_servers

SERIALIZATION_JSON = "json"
SERIALIZATION_STRING = "string"
MIN_FLUSH_TIMEOUT_SECONDS = 1
MAX_FLUSH_TIMEOUT_SECONDS = 300


class ConfluentKafkaProducerComponent(Component):
    """Produce one or more messages to a Kafka topic and return the delivery report."""

    display_name = "Confluent Kafka Producer"
    description = (
        "Publish a Message, Data, or every row of a DataFrame to a Kafka topic on Confluent "
        "Cloud or Confluent Platform, and return the delivery report."
    )
    documentation: str = "https://docs.langflow.org/bundles-confluent"
    icon = "Confluent"
    name = "ConfluentKafkaProducer"
    metadata = {"keywords": ["confluent", "kafka", "producer", "publish", "topic", "streaming", "ibm"]}

    inputs = [
        StrInput(
            name="bootstrap_servers",
            display_name="Bootstrap Servers",
            info="Comma-separated host:port list, for example pkc-xxxxx.us-east-1.aws.confluent.cloud:9092.",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Kafka cluster API key (SASL/PLAIN username). Leave empty for an unauthenticated broker.",
        ),
        SecretStrInput(
            name="api_secret",
            display_name="API Secret",
            info="Kafka cluster API secret (SASL/PLAIN password).",
        ),
        MessageTextInput(
            name="topic",
            display_name="Topic",
            info="Topic to publish to.",
            required=True,
            tool_mode=True,
        ),
        HandleInput(
            name="message",
            display_name="Message",
            info=(
                "What to publish. A Message publishes its text; a Data object publishes its JSON; "
                "a DataFrame publishes one record per row."
            ),
            input_types=["Message", "Data", "DataFrame"],
            required=True,
        ),
        MessageTextInput(
            name="key",
            display_name="Message Key",
            info="Optional record key. Records with the same key land on the same partition.",
            tool_mode=True,
        ),
        DropdownInput(
            name="serialization",
            display_name="Value Serialization",
            options=[SERIALIZATION_JSON, SERIALIZATION_STRING],
            value=SERIALIZATION_JSON,
            info="json: publish objects as UTF-8 JSON. string: publish the text as-is.",
            advanced=True,
        ),
        DictInput(
            name="headers",
            display_name="Record Headers",
            info="Optional Kafka record headers added to every published record.",
            advanced=True,
            is_list=True,
        ),
        IntInput(
            name="flush_timeout",
            display_name="Flush Timeout (seconds)",
            info=(
                "How long to wait for the broker to acknowledge the records "
                f"(clamped to {MIN_FLUSH_TIMEOUT_SECONDS}-{MAX_FLUSH_TIMEOUT_SECONDS}s)."
            ),
            value=10,
            range_spec={"min": MIN_FLUSH_TIMEOUT_SECONDS, "max": MAX_FLUSH_TIMEOUT_SECONDS, "step": 1},
            advanced=True,
        ),
        DictInput(
            name="client_config",
            display_name="Extra Client Config",
            info="Additional librdkafka producer settings, for example {'acks': 'all'}.",
            advanced=True,
            is_list=True,
        ),
    ]

    outputs = [
        Output(display_name="Delivery Report", name="delivery_report", method="produce"),
    ]

    # ----------------------------------------------------------- payloads
    def _records(self) -> list[dict[str, Any]]:
        """Turn the connected input into a list of ``{"key", "value"}`` records."""
        payload = self.message
        base_key = (getattr(self, "key", "") or "").strip() or None
        serialization = getattr(self, "serialization", SERIALIZATION_JSON) or SERIALIZATION_JSON

        def encode(value: Any) -> bytes:
            if serialization == SERIALIZATION_STRING or isinstance(value, str):
                return str(value).encode("utf-8")
            return json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")

        if isinstance(payload, DataFrame):
            rows = payload.to_dict(orient="records")
            return [{"key": base_key, "value": encode(row)} for row in rows]
        if isinstance(payload, Message):
            text = payload.text if payload.text is not None else ""
            return [{"key": base_key, "value": encode(text)}]
        if isinstance(payload, Data):
            data = payload.data if isinstance(payload.data, dict) else {"data": payload.data}
            return [{"key": base_key, "value": encode(data)}]
        if isinstance(payload, list):
            return [
                {"key": base_key, "value": encode(item.data if isinstance(item, Data) else item)} for item in payload
            ]
        if payload is None or payload == "":
            msg = "Connect a Message, Data, or DataFrame to publish."
            raise ValueError(msg)
        return [{"key": base_key, "value": encode(payload)}]

    def _record_headers(self) -> list[tuple[str, bytes]] | None:
        raw = getattr(self, "headers", None) or {}
        if isinstance(raw, list):
            merged: dict[str, Any] = {}
            for item in raw:
                if isinstance(item, dict):
                    merged.update(item)
            raw = merged
        if not isinstance(raw, dict) or not raw:
            return None
        return [(str(k), str(v).encode("utf-8")) for k, v in raw.items() if k]

    # -------------------------------------------------------------- produce
    def _produce_sync(
        self, config: dict, topic: str, records: list[dict[str, Any]], flush_timeout: float
    ) -> list[dict]:
        try:
            from confluent_kafka import KafkaError, KafkaException, Producer
        except ImportError as exc:  # pragma: no cover - exercised on platforms without the wheel
            msg = "confluent-kafka is not installed. Install the lfx-confluent bundle with its dependencies."
            raise ImportError(msg) from exc

        producer = Producer(config)
        reports: list[dict] = []
        headers = self._record_headers()

        def on_delivery(err: KafkaError | None, msg) -> None:
            if err is not None:
                reports.append({"topic": topic, "error": str(err), "delivered": False})
                return
            ts_type, ts_value = msg.timestamp()
            reports.append(
                {
                    "topic": msg.topic(),
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "timestamp": ts_value if ts_type else None,
                    "key": (msg.key() or b"").decode("utf-8", errors="replace") if msg.key() else None,
                    "delivered": True,
                }
            )

        try:
            for record in records:
                key = record["key"].encode("utf-8") if record["key"] else None
                producer.produce(topic, value=record["value"], key=key, headers=headers, on_delivery=on_delivery)
                # Serve delivery callbacks eagerly so a slow broker doesn't fill the local queue.
                producer.poll(0)
            remaining = producer.flush(flush_timeout)
        except (KafkaException, BufferError) as exc:
            msg = f"Kafka produce failed: {exc}"
            raise ValueError(msg) from exc
        if remaining:
            reports.append(
                {
                    "topic": topic,
                    "error": f"{remaining} record(s) not acknowledged within {flush_timeout}s",
                    "delivered": False,
                }
            )
        return reports

    def _flush_timeout(self) -> float:
        """Return the flush timeout, clamped so it can never ask ``flush`` to wait forever.

        ``Producer.flush`` treats a negative timeout as "block until every record is
        acknowledged", which would pin the ``asyncio.to_thread`` worker indefinitely when
        a broker is unreachable. ``range_spec`` only bounds the UI slider, not a value
        arriving from Tool Mode or the API.
        """
        timeout = float(getattr(self, "flush_timeout", 10) or 10)
        return max(float(MIN_FLUSH_TIMEOUT_SECONDS), min(timeout, float(MAX_FLUSH_TIMEOUT_SECONDS)))

    async def produce(self) -> Data:
        bootstrap = validate_bootstrap_servers(self.bootstrap_servers)
        topic = (self.topic or "").strip()
        if not topic:
            msg = "Topic is required."
            raise ValueError(msg)
        records = self._records()
        extra = getattr(self, "client_config", None) or {}
        if isinstance(extra, list):
            merged: dict[str, Any] = {}
            for item in extra:
                if isinstance(item, dict):
                    merged.update(item)
            extra = merged
        config = kafka_client_config(bootstrap, self.api_key, self.api_secret, extra=extra)
        flush_timeout = self._flush_timeout()
        reports = await asyncio.to_thread(self._produce_sync, config, topic, records, flush_timeout)
        delivered = sum(1 for r in reports if r.get("delivered"))
        failed = len(reports) - delivered
        result = Data(
            data={
                "topic": topic,
                "records_sent": len(records),
                "delivered": delivered,
                "failed": failed,
                "reports": reports,
            }
        )
        summary = f"Delivered {delivered}/{len(records)} record(s) to {topic}"
        self.status = f"{summary} ({failed} failed)" if failed else summary
        if failed and not delivered:
            msg = f"No records were delivered to {topic}: {reports[0].get('error', 'unknown error')}"
            raise ValueError(msg)
        return result
