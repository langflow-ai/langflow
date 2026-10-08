"""Cassandra connection targets are checked before cassio opens a driver connection."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_datastax.components.cassandra import (
    CassandraChatMemory,
    CassandraGraphVectorStoreComponent,
    CassandraVectorStoreComponent,
)


@contextmanager
def ssrf_enabled():
    with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get:
        settings = MagicMock()
        settings.settings.ssrf_protection_enabled = True
        settings.settings.connector_ssrf_validation_enabled = True
        settings.settings.connector_ssrf_allow_loopback = True
        settings.settings.ssrf_allowed_hosts = []
        mock_get.return_value = settings
        yield


@pytest.mark.parametrize(
    ("component_class", "method"),
    [
        (CassandraVectorStoreComponent, "build_vector_store"),
        (CassandraChatMemory, "build_message_history"),
        (CassandraGraphVectorStoreComponent, "build_vector_store"),
    ],
)
def test_cassandra_components_block_secondary_metadata_contact_point(component_class, method):
    component = component_class()
    component.database_ref = "8.8.8.8,169.254.169.254"
    component.cluster_kwargs = {"port": 6379}
    with ssrf_enabled(), patch("cassio.init") as mock_init, pytest.raises(SSRFProtectionError):
        getattr(component, method)()
    mock_init.assert_not_called()


@pytest.mark.parametrize(
    ("database_ref", "target_argument"),
    [
        ("127.0.0.1", "contact_points"),
        ("123e4567-e89b-12d3-a456-426614174000", "database_id"),
    ],
)
def test_cassandra_chat_preserves_loopback_and_astra_database_id(database_ref, target_argument):
    component = CassandraChatMemory()
    component.database_ref = database_ref
    component.username = "user"
    component.token = "test-token"
    component.cluster_kwargs = {}
    component.session_id = "session"
    component.table_name = "messages"
    component.keyspace = "default_keyspace"

    with (
        ssrf_enabled(),
        patch("cassio.init") as mock_init,
        patch("langchain_community.chat_message_histories.CassandraChatMessageHistory") as mock_history,
    ):
        assert component.build_message_history() is mock_history.return_value

    assert mock_init.call_count == 1
    assert mock_init.call_args.kwargs[target_argument] == database_ref


def test_cassandra_discovered_peer_is_validated():
    component = CassandraChatMemory()
    component.database_ref = "8.8.8.8"
    component.cluster_kwargs = {}
    component.session_id = "session"
    component.table_name = "messages"
    component.keyspace = "default_keyspace"

    with (
        ssrf_enabled(),
        patch("cassio.init") as mock_init,
        patch("langchain_community.chat_message_histories.CassandraChatMessageHistory"),
    ):
        component.build_message_history()
        translator = mock_init.call_args.kwargs["cluster_kwargs"]["address_translator"]
        assert translator.translate("8.8.8.8") == "8.8.8.8"
        with pytest.raises(SSRFProtectionError):
            translator.translate("169.254.169.254")
