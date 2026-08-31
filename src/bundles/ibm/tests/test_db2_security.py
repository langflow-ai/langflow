"""Unit tests for lightweight DB2 security helpers."""

import ast
import http.server
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lfx_ibm.components.ibm import db2_security
from lfx_ibm.components.ibm.db2_security import (
    create_safe_error_message,
    download_certificate,
    validate_and_prepare_ssl_certificate,
    validate_database_name,
    validate_hostname,
    validate_identifier,
    validate_port,
    validate_ssl_certificate_path,
)


def test_validate_database_name_accepts_valid_name():
    """Database names with safe characters should pass validation."""
    assert validate_database_name("TESTDB") == "TESTDB"


def test_validate_database_name_rejects_unsafe_characters():
    """Unsafe characters should be rejected from database names."""
    with pytest.raises(ValueError, match="unsafe characters"):
        validate_database_name("TESTDB; DROP TABLE users;")


def test_validate_hostname_accepts_valid_hostname():
    """Standard hostnames should pass validation."""
    assert validate_hostname("localhost") == "localhost"


def test_validate_hostname_rejects_unsafe_characters():
    """Unsafe characters should be rejected from hostnames."""
    with pytest.raises(ValueError, match="unsafe characters"):
        validate_hostname("localhost;rm -rf /")


def test_validate_port_accepts_valid_port():
    """Valid TCP ports should pass validation."""
    assert validate_port(50000) == 50000


def test_validate_port_rejects_out_of_range_value():
    """Out-of-range ports should fail validation."""
    with pytest.raises(ValueError, match="between 1 and 65535"):
        validate_port(70000)


def test_validate_identifier_accepts_table_name():
    """Safe SQL identifiers should pass validation."""
    assert validate_identifier("LANGFLOW_VECTORS", "table name") == "LANGFLOW_VECTORS"


def test_validate_identifier_rejects_invalid_identifier():
    """Unsafe table names should fail validation."""
    with pytest.raises(ValueError, match="table name"):
        validate_identifier("invalid-table", "table name")


def test_create_safe_error_message_redacts_connection_details():
    """Sensitive connection string values should be redacted."""
    error = RuntimeError("DATABASE=TESTDB;HOSTNAME=localhost;PORT=50000;UID=db2inst1;PWD=secret")
    message = create_safe_error_message(error, "while connecting to database")

    assert "TESTDB" not in message
    assert "localhost" not in message
    assert "50000" not in message
    assert "db2inst1" not in message
    assert "secret" not in message
    assert "[REDACTED]" in message
    assert "while connecting to database" in message


# ---------------------------------------------------------------------------
# SSL certificate fetch/containment (LE-2247)
#
# ``ssl_certificate_path`` is a tenant-controlled component field.  A published
# flow makes it reachable from the unauthenticated public-build endpoint, so a
# URL value turns into a server-side GET from Langflow's network context, and a
# local path value turns into a server-side file read.  Both branches must be
# constrained.
# ---------------------------------------------------------------------------

# Literal internal targets that the connector SSRF policy blocks regardless of the
# loopback exemption (``connector_ssrf_allow_loopback`` only exempts loopback).
_INTERNAL_TARGETS = (
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata (IMDS)
    "http://10.0.0.1/cert.pem",  # RFC1918
    "http://192.168.1.1/cert.pem",  # RFC1918
)


class _RedirectHandler(http.server.BaseHTTPRequestHandler):
    """Serves a 302 to cloud metadata -- the report's "302 redirector" shape."""

    def log_message(self, *args):
        """Silence the stderr access log."""

    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
        self.end_headers()


@contextmanager
def _redirector():
    """Run a loopback HTTP server that 302-redirects to cloud metadata."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/cert.pem"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@contextmanager
def _restricted_file_access(config_dir: str):
    """Turn on LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS containment for the duration."""
    with patch("lfx.utils.file_path_security.get_settings_service") as mock_get:
        settings = MagicMock()
        settings.settings.restrict_local_file_access = True
        settings.settings.config_dir = config_dir
        settings.settings.database_url = ""
        mock_get.return_value = settings
        yield


@pytest.mark.parametrize("url", _INTERNAL_TARGETS)
def test_download_certificate_blocks_internal_targets(url):
    """A certificate URL pointing at an internal host must not be fetched."""
    path, error = download_certificate(url)

    assert path is None
    assert error is not None
    assert "SSRF" in error


@pytest.mark.parametrize("url", _INTERNAL_TARGETS)
def test_validate_and_prepare_blocks_internal_targets(url):
    """The public entry point used by the components refuses internal targets too."""
    path, is_temp, error = validate_and_prepare_ssl_certificate(url)

    assert path is None
    assert is_temp is False
    assert error is not None
    assert "SSRF" in error


def test_download_certificate_revalidates_redirect_hop():
    """A first hop that is allowed must not smuggle an internal target via 302.

    First-hop-only validation is defeated by an attacker-controlled redirector, so
    every hop has to be re-validated.  Loopback is exempt for connectors by default,
    which is exactly the case a first-hop-only validator would wave through.
    """
    with _redirector() as redirect_url:
        path, error = download_certificate(redirect_url)

    assert path is None, "followed a redirect into cloud metadata"
    assert error is not None
    assert "SSRF" in error


def test_no_raw_urlopen_sink_in_module():
    """The module must not reach the network through raw ``urllib.request``.

    Pins the fix shape: an unguarded request would have to be issued through a raw
    sink, and ``urllib.request`` has no per-hop SSRF validation.
    """
    source = Path(db2_security.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    raw_sinks = [
        f"line {node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in {"urlopen", "urlretrieve", "Request"}
    ]
    assert not raw_sinks, (
        f"db2_security.py uses a raw urllib network sink at {raw_sinks}. "
        "Route certificate downloads through lfx.utils.ssrf_httpx so every hop is validated."
    )
    assert "urllib.request" not in source, "db2_security.py must not import urllib.request"


@pytest.mark.parametrize(
    "cert_path",
    [
        "file:///etc/ssl/cert.pem",
        "ftp://internal.example.com/cert.pem",
        "gopher://127.0.0.1:11211/cert.pem",
        "data:text/plain;base64,Zm9v",
    ],
)
def test_non_http_schemes_rejected(cert_path):
    """Only http(s) URLs are downloadable; other schemes must not fall through."""
    resolved, error = validate_ssl_certificate_path(cert_path)

    assert resolved is None
    assert error is not None
    assert "scheme" in error.lower()


def test_local_path_containment_rejects_path_outside_scope(tmp_path):
    """Under restriction, a certificate outside the caller's storage scope is refused."""
    config_dir = tmp_path / "config"
    (config_dir / "scope-a").mkdir(parents=True)
    outside = tmp_path / "outside.pem"
    outside.write_bytes(b"-----BEGIN CERTIFICATE-----\n")

    with _restricted_file_access(str(config_dir)):
        resolved, error = validate_ssl_certificate_path(str(outside), scope_ids=("scope-a",))

    assert resolved is None
    assert error is not None
    assert "storage scope" in error


def test_local_path_containment_allows_path_inside_scope(tmp_path):
    """Containment is a boundary, not a ban: an in-scope certificate still loads."""
    config_dir = tmp_path / "config"
    scope_dir = config_dir / "scope-a"
    scope_dir.mkdir(parents=True)
    inside = scope_dir / "ca.pem"
    inside.write_bytes(b"-----BEGIN CERTIFICATE-----\n")

    with _restricted_file_access(str(config_dir)):
        resolved, error = validate_ssl_certificate_path(str(inside), scope_ids=("scope-a",))

    assert error is None
    assert resolved == str(inside.resolve())


def test_local_path_unrestricted_default_is_unchanged(tmp_path):
    """With containment off (OSS default) an absolute path keeps working."""
    cert = tmp_path / "ca.pem"
    cert.write_bytes(b"-----BEGIN CERTIFICATE-----\n")

    resolved, error = validate_ssl_certificate_path(str(cert))

    assert error is None
    assert resolved == str(cert.resolve())


# Made with Bob
