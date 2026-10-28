from unittest.mock import patch

import pytest
from lfx_oracle.components.oracle.connection import build_connection_params


@pytest.fixture(autouse=True)
def enable_ssrf(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)


@pytest.mark.parametrize(
    "dsn",
    [
        "169.254.169.254:1521/service",
        "tcp://10.1.2.3:1521/service",
        "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=192.168.1.2)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=service)))",
        "(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=127.0.0.1)(PORT=1521))"
        "(ADDRESS=(PROTOCOL=TCP)(HOST=169.254.169.254)(PORT=1521)))"
        "(CONNECT_DATA=(SERVICE_NAME=service)))",
        "tcps://127.0.0.1:1521/service?https_proxy=169.254.169.254&https_proxy_port=8080",
    ],
)
def test_rejects_blocked_oracle_destinations(dsn):
    with pytest.raises(ValueError, match=r"SSRF|blocked"):
        build_connection_params(dsn=dsn)


@pytest.mark.parametrize("params", [{"host": "10.1.2.3"}, {"https_proxy": "169.254.169.254"}])
def test_rejects_connection_parameter_destinations(params):
    with pytest.raises(ValueError, match=r"SSRF|blocked"):
        build_connection_params(params, dsn="127.0.0.1:1521/service")


def test_rejects_alias_resolving_to_internal_host(tmp_path):
    (tmp_path / "tnsnames.ora").write_text(
        "PRIVATE=(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=10.1.2.3)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=service)))"
    )
    with pytest.raises(ValueError, match=r"SSRF|blocked"):
        build_connection_params({"config_dir": str(tmp_path)}, dsn="PRIVATE")


def test_rejects_public_hostname_resolving_to_internal_host():
    with (
        patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["10.1.2.3"]),
        pytest.raises(ValueError, match="blocked"),
    ):
        build_connection_params(dsn="db.example.test:1521/service")


def test_allows_public_host_and_preserves_connection_arguments():
    with patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["93.184.216.34"]):
        params = build_connection_params(dsn="db.example.test:1521/service", user="user")
    assert params["user"] == "user"
    assert "HOST=db.example.test" in params["dsn"]


def test_allows_operator_approved_internal_host(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "10.1.2.3")
    assert "HOST=10.1.2.3" in build_connection_params(dsn="10.1.2.3:1521/service")["dsn"]


@pytest.mark.parametrize("alias", ["LOCAL", "SAFE:ALIAS", '"SAFE/ALIAS"'])
def test_materializes_validated_alias(tmp_path, alias):
    (tmp_path / "tnsnames.ora").write_text(
        f"{alias}=(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=127.0.0.1)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=service)))"
    )
    params = build_connection_params({"config_dir": str(tmp_path)}, dsn=alias)
    assert "HOST=127.0.0.1" in params["dsn"]
    assert params["dsn"] != alias


def test_rejects_remote_configuration_protocol_before_parsing():
    with patch("oracledb.ConnectParams") as parser, pytest.raises(ValueError, match="TCP"):
        build_connection_params(dsn="config-file://example.com/tnsnames.ora?key=service")
    parser.assert_not_called()


def test_retains_operator_opt_out(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "false")
    assert build_connection_params(dsn="10.1.2.3/service")["dsn"] == "10.1.2.3/service"
