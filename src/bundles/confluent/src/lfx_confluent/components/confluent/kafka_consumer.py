"""Read a bounded batch of Kafka records from Confluent Cloud / Platform into a DataFrame."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.log.logger import logger
from lfx.schema.dataframe import DataFrame
from lfx_confluent.components.confluent._common import (
    ensure_url_allowed,
    kafka_client_config,
    validate_bootstrap_servers,
)

VALUE_FORMAT_JSON = "json"
VALUE_FORMAT_STRING = "string"
VALUE_FORMAT_AVRO = "avro"
VALUE_FORMAT_JSON_SCHEMA = "json_schema"
VALUE_FORMATS = [VALUE_FORMAT_JSON, VALUE_FORMAT_STRING, VALUE_FORMAT_AVRO, VALUE_FORMAT_JSON_SCHEMA]
SCHEMA_REGISTRY_FORMATS = {VALUE_FORMAT_AVRO, VALUE_FORMAT_JSON_SCHEMA}

OFFSET_RESET_OPTIONS = ["latest", "earliest"]
MAX_MESSAGES_CAP = 10_000
MAX_TIMEOUT_SECONDS = 300.0
POLL_SLICE_SECONDS = 1.0


class ConfluentKafkaConsumerComponent(Component):
    """Consume up to N records (or until a timeout) from one or more topics."""

    display_name = "Confluent Kafka Consumer"
    description = (
        "Read a bounded batch of records from Kafka topics on Confluent Cloud or Confluent Platform "
        "into a DataFrame (one row per record). Stops at the message limit or the timeout."
    )
    documentation: str = "https://docs.langflow.org/bundles-confluent"
    icon = "Confluent"
    name = "ConfluentKafkaConsumer"
    metadata = {"keywords": ["confluent", "kafka", "consumer", "subscribe", "topic", "streaming", "ibm"]}

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
            name="topics",
            display_name="Topics",
            info="Comma-separated topic names to subscribe to.",
            required=True,
            tool_mode=True,
        ),
        StrInput(
            name="group_id",
            display_name="Consumer Group ID",
            info="Consumer group used to track offsets. Leave empty to derive one from the flow ID.",
        ),
        IntInput(
            name="max_messages",
            display_name="Max Messages",
            info=f"Stop after this many records (capped at {MAX_MESSAGES_CAP}).",
            value=100,
            range_spec={"min": 1, "max": MAX_MESSAGES_CAP, "step": 1},
            tool_mode=True,
        ),
        FloatInput(
            name="timeout_seconds",
            display_name="Timeout (seconds)",
            info=f"Stop waiting for more records after this long (capped at {MAX_TIMEOUT_SECONDS:g}s).",
            value=5.0,
            range_spec={"min": 0.5, "max": MAX_TIMEOUT_SECONDS, "step": 0.5},
        ),
        DropdownInput(
            name="auto_offset_reset",
            display_name="Start From",
            options=OFFSET_RESET_OPTIONS,
            value="latest",
            info="Where a new consumer group starts: latest (only new records) or earliest (from the beginning).",
            advanced=True,
        ),
        BoolInput(
            name="commit_offsets",
            display_name="Commit Offsets",
            info="Commit the consumed offsets so the next run continues where this one stopped.",
            value=True,
            advanced=True,
        ),
        DropdownInput(
            name="value_format",
            display_name="Value Format",
            options=VALUE_FORMATS,
            value=VALUE_FORMAT_JSON,
            info=(
                "json: parse UTF-8 JSON (falls back to text). string: raw text. avro / json_schema: decode "
                "with Confluent Schema Registry (requires the Schema Registry fields)."
            ),
            real_time_refresh=True,
            advanced=True,
        ),
        StrInput(
            name="schema_registry_url",
            display_name="Schema Registry URL",
            info="Schema Registry endpoint, for example https://psrc-xxxxx.us-east-2.aws.confluent.cloud.",
            advanced=True,
            show=False,
        ),
        SecretStrInput(
            name="schema_registry_key",
            display_name="Schema Registry API Key",
            advanced=True,
            show=False,
        ),
        SecretStrInput(
            name="schema_registry_secret",
            display_name="Schema Registry API Secret",
            advanced=True,
            show=False,
        ),
        DictInput(
            name="client_config",
            display_name="Extra Client Config",
            info="Additional librdkafka consumer settings.",
            advanced=True,
            is_list=True,
        ),
    ]

    outputs = [
        Output(display_name="Records", name="records", method="consume"),
    ]

    # ------------------------------------------------------------ build cfg
    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name == "value_format":
            needs_registry = field_value in SCHEMA_REGISTRY_FORMATS
            for key in ("schema_registry_url", "schema_registry_key", "schema_registry_secret"):
                if key in build_config:
                    build_config[key]["show"] = needs_registry
                    build_config[key]["advanced"] = not needs_registry
        return build_config

    # ------------------------------------------------------------- helpers
    def _resolved_group_id(self) -> str:
        explicit = (getattr(self, "group_id", "") or "").strip()
        if explicit:
            return explicit
        try:
            flow_id = self.flow_id
        except Exception:  # noqa: BLE001 - no graph bound (e.g. unit tests); fall back to a stable name
            flow_id = None
        return f"langflow-{flow_id}" if flow_id else "langflow-consumer"

    def _topic_list(self) -> list[str]:
        topics = [t.strip() for t in (self.topics or "").split(",") if t.strip()]
        if not topics:
            msg = "At least one topic is required."
            raise ValueError(msg)
        return topics

    def _bounds(self) -> tuple[int, float]:
        max_messages = int(getattr(self, "max_messages", 100) or 100)
        max_messages = max(1, min(max_messages, MAX_MESSAGES_CAP))
        timeout = float(getattr(self, "timeout_seconds", 5.0) or 5.0)
        timeout = max(0.5, min(timeout, MAX_TIMEOUT_SECONDS))
        return max_messages, timeout

    def _value_deserializer(self):
        """Return ``callable(topic, raw_bytes) -> Any`` for the configured value format."""
        value_format = getattr(self, "value_format", VALUE_FORMAT_JSON) or VALUE_FORMAT_JSON

        if value_format == VALUE_FORMAT_STRING:
            return lambda _topic, raw: raw.decode("utf-8", errors="replace") if raw is not None else None

        if value_format == VALUE_FORMAT_JSON:

            def decode_json(_topic: str, raw: bytes | None) -> Any:
                if raw is None:
                    return None
                text = raw.decode("utf-8", errors="replace")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text

            return decode_json

        # Schema Registry-backed formats.
        registry_url = ensure_url_allowed(getattr(self, "schema_registry_url", "") or "")
        try:
            from confluent_kafka.schema_registry import SchemaRegistryClient
            from confluent_kafka.serialization import MessageField, SerializationContext
        except ImportError as exc:  # pragma: no cover
            msg = (
                "confluent-kafka Schema Registry support is not installed "
                "(pip install 'confluent-kafka[avro,json,schemaregistry]')."
            )
            raise ImportError(msg) from exc

        registry_config: dict[str, Any] = {"url": registry_url}
        sr_key = (getattr(self, "schema_registry_key", "") or "").strip()
        sr_secret = (getattr(self, "schema_registry_secret", "") or "").strip()
        if sr_key or sr_secret:
            if not sr_key or not sr_secret:
                msg = "Both the Schema Registry API key and secret are required."
                raise ValueError(msg)
            registry_config["basic.auth.user.info"] = f"{sr_key}:{sr_secret}"
        client = SchemaRegistryClient(registry_config)

        if value_format == VALUE_FORMAT_AVRO:
            from confluent_kafka.schema_registry.avro import AvroDeserializer

            deserializer = AvroDeserializer(client)
        elif value_format == VALUE_FORMAT_JSON_SCHEMA:
            from confluent_kafka.schema_registry.json_schema import JSONDeserializer

            deserializer = JSONDeserializer(None, schema_registry_client=client)
        else:
            msg = f"Unsupported value format: {value_format!r}"
            raise ValueError(msg)

        def decode_registry(topic: str, raw: bytes | None) -> Any:
            if raw is None:
                return None
            return deserializer(raw, SerializationContext(topic, MessageField.VALUE))

        return decode_registry

    @staticmethod
    def _row_from_message(msg, value: Any) -> dict[str, Any]:
        ts_type, ts_value = msg.timestamp()
        key = msg.key()
        headers = msg.headers() or []
        row: dict[str, Any] = {
            "topic": msg.topic(),
            "partition": msg.partition(),
            "offset": msg.offset(),
            "timestamp": ts_value if ts_type else None,
            "key": key.decode("utf-8", errors="replace") if isinstance(key, bytes) else key,
            "headers": {k: (v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v) for k, v in headers}
            if headers
            else None,
        }
        if isinstance(value, dict):
            # Promote record fields to columns; keep the raw object under "value" too.
            for k, v in value.items():
                row.setdefault(str(k), v)
            row["value"] = value
        else:
            row["value"] = value
        return row

    # -------------------------------------------------------------- consume
    def _consume_sync(
        self, config: dict, topics: list[str], max_messages: int, timeout: float, *, commit: bool
    ) -> list[dict]:
        try:
            from confluent_kafka import Consumer, KafkaError, KafkaException
        except ImportError as exc:  # pragma: no cover - exercised on platforms without the wheel
            msg = "confluent-kafka is not installed. Install the lfx-confluent bundle with its dependencies."
            raise ImportError(msg) from exc

        decode = self._value_deserializer()
        consumer = Consumer(config)
        rows: list[dict] = []
        try:
            consumer.subscribe(topics)
            deadline = time.monotonic() + timeout
            while len(rows) < max_messages:
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0:
                    break
                batch = consumer.consume(
                    num_messages=max_messages - len(rows),
                    timeout=min(POLL_SLICE_SECONDS, remaining_time),
                )
                for msg in batch:
                    err = msg.error()
                    if err is not None:
                        if err.code() == KafkaError._PARTITION_EOF:  # noqa: SLF001 - documented librdkafka sentinel
                            continue
                        raise KafkaException(err)
                    try:
                        value = decode(msg.topic(), msg.value())
                    except Exception as exc:  # noqa: BLE001 - keep the batch, surface the decode error per row
                        value = None
                        row = self._row_from_message(msg, value)
                        row["decode_error"] = str(exc)
                        rows.append(row)
                        continue
                    rows.append(self._row_from_message(msg, value))
            if commit and rows:
                consumer.commit(asynchronous=False)
        except KafkaException as exc:
            msg = f"Kafka consume failed: {exc}"
            raise ValueError(msg) from exc
        finally:
            consumer.close()
        return rows

    async def consume(self) -> DataFrame:
        bootstrap = validate_bootstrap_servers(self.bootstrap_servers)
        topics = self._topic_list()
        max_messages, timeout = self._bounds()
        extra = getattr(self, "client_config", None) or {}
        if isinstance(extra, list):
            merged: dict[str, Any] = {}
            for item in extra:
                if isinstance(item, dict):
                    merged.update(item)
            extra = merged
        base = {
            "group.id": self._resolved_group_id(),
            "auto.offset.reset": getattr(self, "auto_offset_reset", "latest") or "latest",
            "enable.auto.commit": False,
        }
        base.update(extra)
        config = kafka_client_config(bootstrap, self.api_key, self.api_secret, extra=base)
        commit = bool(getattr(self, "commit_offsets", True))
        rows = await asyncio.to_thread(self._consume_sync, config, topics, max_messages, timeout, commit=commit)
        frame = DataFrame(rows)
        self.status = f"Consumed {len(rows)} record(s) from {', '.join(topics)}"
        if not rows:
            await logger.adebug(f"Kafka consumer read no records from {topics} within {timeout}s")
        return frame
