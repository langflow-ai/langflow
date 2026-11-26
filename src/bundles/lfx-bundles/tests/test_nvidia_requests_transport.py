"""Exercise the native Requests stack up to its TCP and TLS boundaries, entirely offline."""

import io
from unittest.mock import Mock, patch

import pytest
import requests
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_bundles.nvidia._transport import pin_requests_session


def test_pinned_session_keeps_host_tls_and_streaming_with_address_fallback(tmp_path):
    base = "https://bücher.example:8443/v1"
    expected_host = "xn--bcher-kva.example"
    ips = ["2001:db8::1", "192.0.2.1"]
    ca_file = tmp_path / "custom.pem"
    ca_file.touch()
    sock = Mock()
    sock.makefile.return_value = io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\ndata")
    with (
        requests.Session() as session,
        patch("urllib3.connection.connection.create_connection", side_effect=[OSError("unavailable"), sock]) as dial,
        patch("urllib3.connection._ssl_wrap_socket_and_match_hostname", return_value=(sock, True)) as tls,
    ):
        session.trust_env = False
        session.verify = str(ca_file)
        assert pin_requests_session(session, base, ips) is session
        with session.get(base + "/models", stream=True) as response:
            assert not response._content_consumed
            assert list(response.iter_content(chunk_size=2)) == [b"da", b"ta"]
    assert [call.args[0] for call in dial.call_args_list] == [(ip, 8443) for ip in ips]
    assert tls.call_args.kwargs["server_hostname"] == expected_host
    assert tls.call_args.kwargs["ca_certs"] == str(ca_file)
    assert b"Host: xn--bcher-kva.example:8443\r\n" in sock.sendall.call_args.args[0]


def test_proxy_refused_before_connection():
    base = "https://provider.example/v1"
    with (
        requests.Session() as session,
        patch("urllib3.connection.connection.create_connection") as dial,
    ):
        session.trust_env = False
        pin_requests_session(session, base, ["192.0.2.1"])
        with pytest.raises(SSRFProtectionError, match="through a proxy"):
            session.get(base, proxies={"https": "http://proxy.example"})
    dial.assert_not_called()


@pytest.mark.parametrize(
    "url", ["https://provider.example.com/", "https://provider.example:444/", "http://provider.example/"]
)
def test_only_configured_origin_and_explicit_trusted_origin_allowed(url):
    with requests.Session() as session:
        base = "https://provider.example/v1"
        trusted = "https://poll.example"
        pin_requests_session(session, base, ["192.0.2.1"], trusted_origins=(trusted,))

        def get_pool(target):
            request = requests.Request("GET", target).prepare()
            return session.get_adapter(target).get_connection_with_tls_context(request, verify=True)

        with pytest.raises(SSRFProtectionError, match="outside the validated provider origin"):
            get_pool(url)
        poll_pool = get_pool(trusted + "/status")
        assert poll_pool.ConnectionCls is type(poll_pool).ConnectionCls
        provider_pool = get_pool("https://provider.example:443/models")
        assert provider_pool.ConnectionCls is not type(provider_pool).ConnectionCls


def test_adapter_without_tls_pool_hook_fails_closed():
    with requests.Session() as session:
        adapter = session.get_adapter("https://provider.example")
        with (
            patch.object(adapter, "get_connection_with_tls_context", None),
            pytest.raises(SSRFProtectionError, match=r"Requests 2\.32\.2 or newer"),
        ):
            pin_requests_session(session, "https://provider.example", ["192.0.2.1"])
