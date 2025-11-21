import json

from kafka import KafkaConsumer, KafkaProducer

from langflow.custom import Component
from langflow.io import DropdownInput, IntInput, MultilineInput, Output, StrInput
from langflow.schema import Data


class KafkaComponent(Component):
    display_name = "Kafka"
    description = "Interact with Kafka to produce or consume messages."
    icon = "server"
    name = "Kafka"

    inputs = [
        StrInput(
            name="broker",
            display_name="Broker",
            info="Kafka broker address (e.g., 'localhost:9092').",
        ),
        StrInput(
            name="topic",
            display_name="Topic",
            info="Kafka topic to produce/consume messages.",
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            info="Select 'Produce' to send a message or 'Consume' to read messages from the topic.",
            options=["Produce", "Consume"],
            value="Produce",
        ),
        MultilineInput(
            name="message",
            display_name="Message",
            info="Payload to send when in Produce mode. Leave empty for Consume mode.",
        ),
        StrInput(
            name="group_id",
            display_name="Consumer Group",
            info="Consumer group id (only used in Consume mode).",
            value="default-group",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="Timeout for the operation in seconds.",
            value=5,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="execute_kafka", method="execute_kafka"),
    ]

    def execute_kafka(self) -> Data | list[Data]:
        if self.mode == "Produce":
            try:
                producer = KafkaProducer(
                    bootstrap_servers=self.broker, value_serializer=lambda v: json.dumps(v).encode("utf-8")
                )
                if self.message:
                    payload = self.message
                    future = producer.send(self.topic, {"message": payload})
                    result = future.get(timeout=self.timeout)
                    self.status = f"Message produced to partition {result.partition} at offset {result.offset}"
                else:
                    self.status = "No message provided for production."
                producer.flush()
                return Data(data={"result": self.status})
            except Exception as e:
                self.status = str(e)
                raise ValueError(f"Kafka produce error: {e}") from e

        elif self.mode == "Consume":
            try:
                consumer = KafkaConsumer(
                    self.topic,
                    bootstrap_servers=self.broker,
                    group_id=self.group_id,
                    auto_offset_reset="earliest",
                    consumer_timeout_ms=self.timeout * 1000,
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                )
                messages = []
                for msg in consumer:
                    messages.append(msg.value)
                consumer.close()
                self.status = messages if messages else "No messages received."
                return Data(data={"result": self.status})
            except Exception as e:
                self.status = str(e)
                raise ValueError(f"Kafka consume error: {e}") from e

        else:
            msg = f"Unsupported mode: {self.mode}"
            self.status = msg
            raise ValueError(msg)
