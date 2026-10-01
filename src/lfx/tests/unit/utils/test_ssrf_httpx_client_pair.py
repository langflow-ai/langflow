"""Exercise paired clients with real TLS and the protected transport."""

import ssl
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lfx.utils import ssrf_httpx


@pytest.fixture
def tls_endpoint(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    certificate_file = tmp_path / "certificate.pem"
    certificate_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file = tmp_path / "key.pem"
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/metadata")
            else:
                self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate_file, key_file)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, certificate_file
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _clients(url, *, pinned):
    # Local endpoint and pins are controlled by this fixture; URL-policy behavior
    # is covered separately by the public helper's validation tests.
    with patch.object(ssrf_httpx, "is_ssrf_protection_enabled", return_value=True):
        sync_kwargs, async_kwargs = ssrf_httpx._httpx_client_kwargs_for_validated_url(
            url, ["127.0.0.1"] if pinned else []
        )
    return httpx.Client(**sync_kwargs), httpx.AsyncClient(**async_kwargs)


@pytest.mark.parametrize("pinned", [True, False])
async def test_context_is_shared_only_within_one_pair(pinned):
    with patch.object(ssrf_httpx, "create_ssl_context", wraps=ssrf_httpx.create_ssl_context) as create_context:
        sync, asynchronous = _clients("https://localhost:1234", pinned=pinned)
        next_sync, next_asynchronous = _clients("https://localhost:1234", pinned=pinned)
    try:
        context = sync._transport._pool._ssl_context
        assert context is asynchronous._transport._pool._ssl_context
        assert context is not next_sync._transport._pool._ssl_context
        assert next_sync._transport._pool._ssl_context is next_asynchronous._transport._pool._ssl_context
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname
        assert create_context.call_count == 2
    finally:
        sync.close()
        next_sync.close()
        await asynchronous.aclose()
        await next_asynchronous.aclose()


@pytest.mark.parametrize("pinned", [True, False])
@pytest.mark.parametrize("trusted", [True, False])
async def test_real_https_keeps_environment_trust_and_certificate_validation(
    tls_endpoint, monkeypatch, pinned, trusted
):
    port, certificate = tls_endpoint
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    if trusted:
        monkeypatch.setenv("SSL_CERT_FILE", str(certificate))
    else:
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    url = f"https://localhost:{port}"
    sync, asynchronous = _clients(url, pinned=pinned)
    try:
        if trusted:
            assert sync.get(url).status_code == 200
            assert (await asynchronous.get(url)).status_code == 200
            assert sync.get(f"{url}/redirect").status_code == 302
            assert (await asynchronous.get(f"{url}/redirect")).status_code == 302
        else:
            with pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
                sync.get(url)
            with pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
                await asynchronous.get(url)
    finally:
        sync.close()
        await asynchronous.aclose()


@pytest.mark.parametrize("pinned", [True, False])
async def test_real_https_still_checks_hostname(tls_endpoint, monkeypatch, pinned):
    port, certificate = tls_endpoint
    monkeypatch.setenv("SSL_CERT_FILE", str(certificate))
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    url = f"https://127.0.0.1:{port}"
    sync, asynchronous = _clients(url, pinned=pinned)
    try:
        with pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
            sync.get(url)
        with pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
            await asynchronous.get(url)
    finally:
        sync.close()
        await asynchronous.aclose()


async def test_real_pinned_clients_reject_an_unmapped_host(tls_endpoint, monkeypatch):
    port, certificate = tls_endpoint
    monkeypatch.setenv("SSL_CERT_FILE", str(certificate))
    url = f"https://localhost:{port}"
    sync, asynchronous = _clients(url, pinned=True)
    try:
        assert sync._transport.pinned_ips == asynchronous._transport.pinned_ips == {"localhost": ["127.0.0.1"]}
        with pytest.raises(RuntimeError, match="not in the pin map"):
            sync.get(f"https://127.0.0.1:{port}")
        with pytest.raises(RuntimeError, match="not in the pin map"):
            await asynchronous.get(f"https://127.0.0.1:{port}")
    finally:
        sync.close()
        await asynchronous.aclose()


async def test_environment_certificate_directory_is_loaded_once(tmp_path, monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path))
    loads = []
    original_load = ssl.SSLContext.load_verify_locations

    def record_load(context, *args, **kwargs):
        loads.append((args, kwargs))
        return original_load(context, *args, **kwargs)

    monkeypatch.setattr(ssl.SSLContext, "load_verify_locations", record_load)
    sync, asynchronous = _clients("https://localhost:1234", pinned=True)
    try:
        assert len(loads) == 1
        args, kwargs = loads[0]
        assert kwargs.get("capath", args[1] if len(args) > 1 else None) == str(tmp_path)
        assert sync._transport._pool._ssl_context is asynchronous._transport._pool._ssl_context
    finally:
        sync.close()
        await asynchronous.aclose()


def test_disabled_protection_does_not_construct_a_context():
    with (
        patch.object(ssrf_httpx, "is_ssrf_protection_enabled", return_value=False),
        patch.object(ssrf_httpx, "create_ssl_context") as create_context,
    ):
        assert ssrf_httpx._httpx_client_kwargs_for_validated_url("https://localhost:1234", []) == ({}, {})
    create_context.assert_not_called()
