"""SSRF-block regression tests for the DataStax Data API connector path.

``api_endpoint`` (and a ``https://``-prefixed ``database_name``) are tenant-controlled fields on
every AstraDB / HCD component, and the resolved URL is handed to the astrapy client together with
the configured Astra application token. These tests prove the shared connector SSRF guard now runs
at the endpoint-resolution boundary in :class:`AstraDBBaseComponent`, so a blocked destination is
rejected BEFORE any client is constructed and before the token can leave the process.

Only the settings service (to pin SSRF protection on) and the network sink (as a sentinel asserted
never to be reached) are mocked -- the real SSRF validation logic runs.

The sibling ``astradb_cql`` REST path already had this guard; see
``lfx/tests/unit/utils/test_ssrf_protection.py`` for the validator's own coverage.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_datastax")

# 169.254.169.254 (cloud metadata) and 10.0.0.5 (RFC1918) are blocked regardless of
# ``connector_ssrf_allow_loopback``, which defaults to True and would exempt 127.0.0.1.
METADATA_ENDPOINT = "http://169.254.169.254"
PRIVATE_ENDPOINT = "https://10.0.0.5:8080"
PUBLIC_ENDPOINT = "https://db-id-1234.apps.astra.datastax.com"
FAKE_TOKEN = "AstraCS:regression-test-token"  # pragma: allowlist secret


@contextmanager
def ssrf_enabled(allowed_hosts: list[str] | None = None):
    """Enable global and connector SSRF protection."""
    with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get:
        s = MagicMock()
        s.settings.ssrf_protection_enabled = True
        s.settings.connector_ssrf_validation_enabled = True
        s.settings.connector_ssrf_allow_loopback = True
        s.settings.ssrf_allowed_hosts = allowed_hosts or []
        s.settings.restrict_local_file_access = False
        mock_get.return_value = s
        yield


def _component(**attrs):
    from lfx_datastax.base import AstraDBBaseComponent

    component = AstraDBBaseComponent()
    component.token = FAKE_TOKEN
    component.environment = "prod"
    component.database_name = None
    component.api_endpoint = None
    component.keyspace = "default_keyspace"
    component.log = MagicMock()
    for key, value in attrs.items():
        setattr(component, key, value)
    return component


@pytest.mark.parametrize("blocked", [METADATA_ENDPOINT, PRIVATE_ENDPOINT])
def test_get_api_endpoint_blocks_internal_host(blocked):
    """The advanced ``api_endpoint`` field cannot resolve to a guard-blocked host."""
    from lfx.utils.ssrf_protection import SSRFProtectionError

    component = _component(api_endpoint=blocked, database_name="ignored")
    with ssrf_enabled(), pytest.raises(SSRFProtectionError):
        component.get_api_endpoint()


@pytest.mark.parametrize("blocked", ["https://169.254.169.254", "https://10.0.0.5:8080"])
def test_get_api_endpoint_blocks_url_shaped_database_name(blocked):
    """A ``https://``-prefixed ``database_name`` is the same tenant-controlled sink."""
    from lfx.utils.ssrf_protection import SSRFProtectionError

    component = _component(database_name=blocked)
    with ssrf_enabled(), pytest.raises(SSRFProtectionError):
        component.get_api_endpoint()


def test_get_database_object_blocks_before_client_is_built():
    """No astrapy client is constructed -- so the Astra token never leaves the process."""
    from lfx.utils.ssrf_protection import SSRFProtectionError

    component = _component(api_endpoint=METADATA_ENDPOINT)
    with (
        ssrf_enabled(),
        patch("lfx_datastax.base.astradb_base.DataAPIClient") as mock_client,
        pytest.raises(SSRFProtectionError),
    ):
        component.get_database_object()
    assert mock_client.call_count == 0


def test_get_database_object_blocks_explicit_api_endpoint_argument():
    """``get_database_object(api_endpoint=...)`` is fed build_config values, so guard it too."""
    from lfx.utils.ssrf_protection import SSRFProtectionError

    component = _component(api_endpoint=PUBLIC_ENDPOINT)
    with (
        ssrf_enabled(),
        patch("lfx_datastax.base.astradb_base.DataAPIClient") as mock_client,
        pytest.raises(SSRFProtectionError),
    ):
        component.get_database_object(api_endpoint=PRIVATE_ENDPOINT)
    assert mock_client.call_count == 0


def test_collection_data_blocks_before_client_is_built():
    """``collection_data`` builds its own client from the resolved endpoint."""
    from lfx.utils.ssrf_protection import SSRFProtectionError

    component = _component(api_endpoint=METADATA_ENDPOINT)
    with (
        ssrf_enabled(),
        patch("lfx_datastax.base.astradb_base.DataAPIClient") as mock_client,
        pytest.raises(SSRFProtectionError),
    ):
        component.collection_data(collection_name="col")
    assert mock_client.call_count == 0


def test_get_vectorize_providers_blocks_before_admin_client_is_built():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_datastax.base import AstraDBBaseComponent

    with (
        ssrf_enabled(),
        patch("lfx_datastax.base.astradb_base.DataAPIClient") as mock_client,
        pytest.raises(SSRFProtectionError),
    ):
        AstraDBBaseComponent.get_vectorize_providers(
            token=FAKE_TOKEN, environment="prod", api_endpoint=METADATA_ENDPOINT
        )
    assert mock_client.call_count == 0


async def test_create_collection_api_blocks_before_environment_is_built():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_datastax.base import AstraDBBaseComponent

    with (
        ssrf_enabled(),
        patch("lfx_datastax.base.astradb_base._AstraDBCollectionEnvironment") as mock_env,
        pytest.raises(SSRFProtectionError),
    ):
        await AstraDBBaseComponent.create_collection_api(
            new_collection_name="col",
            token=FAKE_TOKEN,
            api_endpoint=METADATA_ENDPOINT,
            environment="prod",
            dimension=4,
        )
    assert mock_env.call_count == 0


async def test_data_api_create_collection_override_blocks_before_client_is_built():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_datastax.components.datastax.astradb_data_api import AstraDBDataAPIComponent

    with (
        ssrf_enabled(),
        patch("lfx_datastax.components.datastax.astradb_data_api.DataAPIClient") as mock_client,
        pytest.raises(SSRFProtectionError),
    ):
        await AstraDBDataAPIComponent.create_collection_api(
            new_collection_name="col",
            token=FAKE_TOKEN,
            api_endpoint=METADATA_ENDPOINT,
            environment="prod",
            dimension=4,
        )
    assert mock_client.call_count == 0


def test_hcd_vector_store_blocks_internal_api_endpoint():
    """HCD takes a free-form API endpoint and forwards it plus credentials to astrapy."""
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_datastax.components.datastax.hcd import HCDVectorStoreComponent

    component = HCDVectorStoreComponent()
    component.collection_name = "col"
    component.username = "hcd-superuser"
    component.password = "hcd-password"  # noqa: S105  # pragma: allowlist secret
    component.api_endpoint = METADATA_ENDPOINT
    component.namespace = None
    component.ca_certificate = None
    component.embedding = MagicMock()
    component.ingest_data = []
    component.log = MagicMock()

    with ssrf_enabled(), pytest.raises(SSRFProtectionError):
        component.build_vector_store()


def test_allowlisted_endpoint_still_resolves():
    """The documented escape hatch keeps private-network Astra/HCD deployments working.

    Uses the allowlist rather than a live public host so the assertion needs no DNS.
    """
    component = _component(api_endpoint=PUBLIC_ENDPOINT)
    with ssrf_enabled(allowed_hosts=["*.apps.astra.datastax.com"]):
        assert component.get_api_endpoint() == PUBLIC_ENDPOINT

    component = _component(api_endpoint=PRIVATE_ENDPOINT)
    with ssrf_enabled(allowed_hosts=["10.0.0.0/8"]):
        assert component.get_api_endpoint() == PRIVATE_ENDPOINT


def test_no_endpoint_configured_still_returns_none():
    """An unset endpoint must stay a no-op rather than raising out of build_config paths."""
    component = _component()
    with ssrf_enabled():
        assert component.get_api_endpoint() is None
