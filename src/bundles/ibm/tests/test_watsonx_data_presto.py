"""Unit tests for ``WatsonxDataPrestoComponent`` (``lfx-ibm``).

``prestodb.dbapi.connect`` is patched with a fake connection so the tests
cover connection-argument construction (auth modes, TLS verification, CA
bundle), the row-limit contract, SSRF gating, and error wrapping without a
Presto engine.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_ibm import WatsonxDataPrestoComponent
from lfx_ibm.components.ibm.watsonx_data_presto import DEFAULT_API_KEY_USERNAME

CONNECT_TARGET = "prestodb.dbapi.connect"


class _FakeCursor:
    def __init__(self, rows, columns):
        self._rows, self._columns = rows, columns
        self.executed = None
        self.fetch_size = None

    def execute(self, query):
        self.executed = query

    @property
    def description(self):
        return [(c, None, None, None, None, None, None) for c in self._columns]

    def fetchmany(self, size):
        self.fetch_size = size
        return self._rows[:size]


class _FakeConnection:
    last: _FakeConnection | None = None

    def __init__(self, rows=None, columns=None, **kwargs):
        self.kwargs = kwargs
        self._http_session = SimpleNamespace(verify=True)
        self.cursor_obj = _FakeCursor(rows or [(1, "a"), (2, "b"), (3, "c")], columns or ["id", "name"])
        self.closed = False
        _FakeConnection.last = self

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def _fake_connect(**kwargs):
    return _FakeConnection(**kwargs)


@pytest.fixture
def component() -> WatsonxDataPrestoComponent:
    c = WatsonxDataPrestoComponent()
    c.host = "presto.example.lakehouse.cloud.ibm.com"
    c.port = 443
    c.catalog = "iceberg_data"
    c.schema_name = "sales"
    c.auth_mode = "api_key"
    c.username = DEFAULT_API_KEY_USERNAME
    c.api_key = "iam-key"  # pragma: allowlist secret
    c.password = ""
    c.query = "SELECT * FROM orders"
    c.max_rows = 2
    c.verify_ssl = True
    c.ssl_ca_file = ""
    c.request_timeout = 30
    return c


def test_component_metadata():
    assert WatsonxDataPrestoComponent.__name__ == "WatsonxDataPrestoComponent"
    assert WatsonxDataPrestoComponent.name == "WatsonxDataPresto"


def test_update_build_config_toggles_password_and_api_key(component):
    build_config = {"password": {"show": False}, "api_key": {"show": True}, "username": {"value": ""}}
    out = component.update_build_config(dict(build_config), "basic", field_name="auth_mode")
    assert out["password"]["show"] is True
    assert out["api_key"]["show"] is False
    out = component.update_build_config(dict(build_config), "api_key", field_name="auth_mode")
    assert out["password"]["show"] is False
    assert out["api_key"]["show"] is True
    assert out["username"]["value"] == DEFAULT_API_KEY_USERNAME


def test_credentials_api_key_mode_defaults_username(component):
    component.username = ""
    assert component._credentials() == (DEFAULT_API_KEY_USERNAME, "iam-key")


def test_credentials_api_key_mode_requires_key(component):
    component.api_key = ""
    with pytest.raises(ValueError, match="IBM Cloud API Key is required"):
        component._credentials()


def test_credentials_basic_mode(component):
    component.auth_mode = "basic"
    component.username = "alice"
    component.password = "pw"  # noqa: S105  # pragma: allowlist secret
    assert component._credentials() == ("alice", "pw")
    component.password = ""
    with pytest.raises(ValueError, match="User Name and Password"):
        component._credentials()


def test_connection_kwargs_shape(component):
    kwargs = component._connection_kwargs()
    assert kwargs["host"] == "presto.example.lakehouse.cloud.ibm.com"
    assert kwargs["port"] == 443
    assert kwargs["http_scheme"] == "https"
    assert kwargs["catalog"] == "iceberg_data"
    assert kwargs["schema"] == "sales"
    assert kwargs["user"] == DEFAULT_API_KEY_USERNAME
    assert kwargs["_password"] == "iam-key"  # noqa: S105  # pragma: allowlist secret
    assert kwargs["request_timeout"] == 30.0


def test_connection_kwargs_blocks_ssrf_host(component):
    component.host = "169.254.169.254"
    with pytest.raises(SSRFProtectionError):
        component._connection_kwargs()


def test_connection_kwargs_rejects_bad_hostname(component):
    component.host = "bad host/../x"
    with pytest.raises(ValueError, match="Invalid hostname"):
        component._connection_kwargs()


async def test_run_query_returns_dataframe_and_respects_max_rows(component):
    with patch(CONNECT_TARGET, side_effect=_fake_connect):
        frame = await component.run_query()
    conn = _FakeConnection.last
    assert conn.kwargs["host"] == component.host
    assert conn.kwargs["auth"].__class__.__name__ == "BasicAuthentication"
    assert "_password" not in conn.kwargs
    assert conn.cursor_obj.executed == "SELECT * FROM orders"
    assert conn.cursor_obj.fetch_size == 2
    assert conn.closed is True
    assert conn._http_session.verify is True
    assert frame.to_dict(orient="records") == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]


async def test_run_query_preserves_duplicate_column_names(component):
    """``SELECT a.id, b.id`` must not collapse into one key and drop the second value."""
    component.max_rows = 1

    def _connect_with_duplicates(**kwargs):
        return _FakeConnection(rows=[(1, 2, 3)], columns=["id", "id", "id"], **kwargs)

    with patch(CONNECT_TARGET, side_effect=_connect_with_duplicates):
        frame = await component.run_query()
    assert frame.to_dict(orient="records") == [{"id": 1, "id_1": 2, "id_2": 3}]


async def test_run_query_disables_tls_verification_when_asked(component):
    component.verify_ssl = False
    with patch(CONNECT_TARGET, side_effect=_fake_connect):
        await component.run_query()
    assert _FakeConnection.last._http_session.verify is False


async def test_run_query_uses_ca_bundle_path(component, tmp_path):
    ca = tmp_path / "ca.crt"
    ca.write_text("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n")
    component.ssl_ca_file = str(ca)
    with patch(CONNECT_TARGET, side_effect=_fake_connect):
        await component.run_query()
    assert _FakeConnection.last._http_session.verify == str(ca)


async def test_run_query_wraps_driver_errors(component):
    def _boom(**_kwargs):
        msg = "engine unavailable"
        raise RuntimeError(msg)

    with (
        patch(CONNECT_TARGET, side_effect=_boom),
        pytest.raises(ValueError, match=r"watsonx\.data Presto query failed"),
    ):
        await component.run_query()


async def test_run_query_requires_sql(component):
    component.query = "   "
    with pytest.raises(ValueError, match="SQL Query is required"):
        await component.run_query()


async def test_downloaded_ca_bundle_is_removed_after_a_successful_query(component, tmp_path):
    """A CA file fetched over HTTP lives in a temp file the component must clean up.

    ``validate_and_prepare_ssl_certificate`` reports ownership through its ``is_temp`` flag;
    discarding it leaks one file per query and can exhaust temporary storage.
    """
    temp_cert = tmp_path / "downloaded.crt"
    temp_cert.write_text("-----BEGIN CERTIFICATE-----")
    component.ssl_ca_file = "https://certs.example.com/ca.pem"

    with (
        patch(
            "lfx_ibm.components.ibm.watsonx_data_presto.validate_and_prepare_ssl_certificate",
            return_value=(str(temp_cert), True, None),
        ),
        patch(CONNECT_TARGET, side_effect=_fake_connect),
    ):
        await component.run_query()

    assert not temp_cert.exists(), "the downloaded CA bundle outlived the query"


async def test_downloaded_ca_bundle_is_removed_when_the_query_fails(component, tmp_path):
    """Cleanup must also happen on the failure path, which is where leaks accumulate."""
    temp_cert = tmp_path / "downloaded.crt"
    temp_cert.write_text("-----BEGIN CERTIFICATE-----")
    component.ssl_ca_file = "https://certs.example.com/ca.pem"

    def _boom(**_kwargs):
        msg = "connection refused"
        raise RuntimeError(msg)

    with (
        patch(
            "lfx_ibm.components.ibm.watsonx_data_presto.validate_and_prepare_ssl_certificate",
            return_value=(str(temp_cert), True, None),
        ),
        patch(CONNECT_TARGET, side_effect=_boom),
        pytest.raises(ValueError, match="Presto query failed"),
    ):
        await component.run_query()

    assert not temp_cert.exists(), "the downloaded CA bundle outlived a failed query"


async def test_operator_supplied_ca_path_is_never_deleted(component, tmp_path):
    """A local CA path belongs to the operator: is_temp is False and it must survive."""
    local_cert = tmp_path / "corporate-ca.pem"
    local_cert.write_text("-----BEGIN CERTIFICATE-----")
    component.ssl_ca_file = str(local_cert)

    with (
        patch(
            "lfx_ibm.components.ibm.watsonx_data_presto.validate_and_prepare_ssl_certificate",
            return_value=(str(local_cert), False, None),
        ),
        patch(CONNECT_TARGET, side_effect=_fake_connect),
    ):
        await component.run_query()

    assert local_cert.exists(), "an operator-owned CA file must not be deleted"
