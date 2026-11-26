"""Unit tests for reserved Kafka client settings."""

import pytest
from lfx_confluent.components.confluent._common import kafka_client_config


@pytest.mark.parametrize("name", ["plugin.library.paths", " Plugin.Library.Paths "])
def test_kafka_client_config_rejects_plugin_settings(name: str) -> None:
    with pytest.raises(ValueError, match="cannot override"):
        kafka_client_config("broker.example:9092", "", "", extra={name: "placeholder"})
