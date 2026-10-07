"""Tests for the DNS-pinning httpx transports (IDN pin-key normalization + fail-closed)."""

import httpcore
import pytest
from lfx.utils.ssrf_transport import (
    DNSPinningNetworkBackend,
    DNSPinningSyncNetworkBackend,
    pin_host_for_url,
)

IDN_URL = "http://exämple-rebind.test/path"
IDN_PUNYCODE_HOST = "xn--exmple-rebind-cfb.test"
PINNED_IP = "93.184.216.34"


class _RecordingAsyncBackend:
    def __init__(self):
        self.connections: list[tuple[str, int]] = []

    async def connect_tcp(self, host, port, **_kwargs):
        self.connections.append((host, port))
        return object()

    async def connect_unix_socket(self, path, **_kwargs):
        raise NotImplementedError

    async def sleep(self, _seconds):
        return None


class _RecordingSyncBackend:
    def __init__(self):
        self.connections: list[tuple[str, int]] = []

    def connect_tcp(self, host, port, **_kwargs):
        self.connections.append((host, port))
        return object()

    def connect_unix_socket(self, path, **_kwargs):
        raise NotImplementedError

    def sleep(self, _seconds):
        return None


class _FailFirstAsyncBackend(_RecordingAsyncBackend):
    def __init__(self, error):
        super().__init__()
        self.error = error

    async def connect_tcp(self, host, port, **_kwargs):
        self.connections.append((host, port))
        if len(self.connections) == 1:
            raise self.error
        return object()


class _FailFirstSyncBackend(_RecordingSyncBackend):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def connect_tcp(self, host, port, **_kwargs):
        self.connections.append((host, port))
        if len(self.connections) == 1:
            raise self.error
        return object()


class TestPinHostForUrl:
    def test_idn_url_returns_punycode_host(self):
        # httpx/httpcore connect to the IDNA form; the pin map must key on it.
        assert pin_host_for_url(IDN_URL) == IDN_PUNYCODE_HOST

    def test_ascii_url_returns_plain_host(self):
        assert pin_host_for_url("https://example.com/path?q=1") == "example.com"


class TestAsyncDNSPinningBackend:
    async def test_connect_uses_pinned_ip_for_punycode_host(self):
        inner = _RecordingAsyncBackend()
        backend = DNSPinningNetworkBackend(pinned_ips={IDN_PUNYCODE_HOST: [PINNED_IP]}, backend=inner)

        await backend.connect_tcp(IDN_PUNYCODE_HOST, 80)

        assert inner.connections == [(PINNED_IP, 80)]

    @pytest.mark.parametrize("error_type", [httpcore.ConnectError, httpcore.ConnectTimeout])
    async def test_connect_tries_next_pinned_ip_after_httpcore_failure(self, error_type):
        inner = _FailFirstAsyncBackend(error_type("first address unavailable"))
        backend = DNSPinningNetworkBackend(
            pinned_ips={"example.com": ["2606:4700:4700::1111", "1.1.1.1"]}, backend=inner
        )

        await backend.connect_tcp("example.com", 80)

        assert inner.connections == [("2606:4700:4700::1111", 80), ("1.1.1.1", 80)]

    async def test_miss_with_non_empty_map_fails_closed(self):
        inner = _RecordingAsyncBackend()
        backend = DNSPinningNetworkBackend(pinned_ips={IDN_PUNYCODE_HOST: [PINNED_IP]}, backend=inner)

        with pytest.raises(RuntimeError, match="not in the pin map"):
            await backend.connect_tcp("other-host.test", 80)

        assert inner.connections == []

    async def test_miss_with_empty_map_passes_through(self):
        inner = _RecordingAsyncBackend()
        backend = DNSPinningNetworkBackend(pinned_ips={}, backend=inner)

        await backend.connect_tcp("allowlisted.test", 80)

        assert inner.connections == [("allowlisted.test", 80)]

    async def test_miss_with_fail_closed_false_passes_through(self):
        inner = _RecordingAsyncBackend()
        backend = DNSPinningNetworkBackend(
            pinned_ips={IDN_PUNYCODE_HOST: [PINNED_IP]}, backend=inner, fail_closed=False
        )

        await backend.connect_tcp("other-host.test", 80)

        assert inner.connections == [("other-host.test", 80)]

    async def test_pinned_host_with_empty_ip_list_raises(self):
        inner = _RecordingAsyncBackend()
        backend = DNSPinningNetworkBackend(pinned_ips={"example.com": []}, backend=inner)

        with pytest.raises(RuntimeError, match="no pinned IPs"):
            await backend.connect_tcp("example.com", 80)

        assert inner.connections == []


class TestSyncDNSPinningBackend:
    def test_connect_uses_pinned_ip_for_punycode_host(self):
        inner = _RecordingSyncBackend()
        backend = DNSPinningSyncNetworkBackend(pinned_ips={IDN_PUNYCODE_HOST: [PINNED_IP]}, backend=inner)

        backend.connect_tcp(IDN_PUNYCODE_HOST, 80)

        assert inner.connections == [(PINNED_IP, 80)]

    @pytest.mark.parametrize("error_type", [httpcore.ConnectError, httpcore.ConnectTimeout])
    def test_connect_tries_next_pinned_ip_after_httpcore_failure(self, error_type):
        inner = _FailFirstSyncBackend(error_type("first address unavailable"))
        backend = DNSPinningSyncNetworkBackend(
            pinned_ips={"example.com": ["2606:4700:4700::1111", "1.1.1.1"]}, backend=inner
        )

        backend.connect_tcp("example.com", 80)

        assert inner.connections == [("2606:4700:4700::1111", 80), ("1.1.1.1", 80)]

    def test_miss_with_non_empty_map_fails_closed(self):
        inner = _RecordingSyncBackend()
        backend = DNSPinningSyncNetworkBackend(pinned_ips={IDN_PUNYCODE_HOST: [PINNED_IP]}, backend=inner)

        with pytest.raises(RuntimeError, match="not in the pin map"):
            backend.connect_tcp("other-host.test", 80)

        assert inner.connections == []

    def test_miss_with_empty_map_passes_through(self):
        inner = _RecordingSyncBackend()
        backend = DNSPinningSyncNetworkBackend(pinned_ips={}, backend=inner)

        backend.connect_tcp("allowlisted.test", 80)

        assert inner.connections == [("allowlisted.test", 80)]

    def test_miss_with_fail_closed_false_passes_through(self):
        inner = _RecordingSyncBackend()
        backend = DNSPinningSyncNetworkBackend(
            pinned_ips={IDN_PUNYCODE_HOST: [PINNED_IP]}, backend=inner, fail_closed=False
        )

        backend.connect_tcp("other-host.test", 80)

        assert inner.connections == [("other-host.test", 80)]

    def test_pinned_host_with_empty_ip_list_raises(self):
        inner = _RecordingSyncBackend()
        backend = DNSPinningSyncNetworkBackend(pinned_ips={"example.com": []}, backend=inner)

        with pytest.raises(RuntimeError, match="no pinned IPs"):
            backend.connect_tcp("example.com", 80)

        assert inner.connections == []
