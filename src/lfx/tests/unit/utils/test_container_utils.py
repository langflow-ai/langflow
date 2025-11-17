"""Test container detection and URL transformation utilities."""

import socket
from pathlib import Path
from unittest.mock import mock_open, patch

from lfx.utils.util import detect_container_environment, get_container_host, transform_localhost_url


class TestDetectContainerEnvironment:
    """Test the detect_container_environment function."""

    def test_detects_docker_via_dockerenv(self):
        """Test detection of Docker via .dockerenv file."""
        with patch.object(Path, "exists", return_value=True):
            result = detect_container_environment()
            assert result == "docker"

    def test_detects_docker_via_cgroup(self):
        """Test detection of Docker via /proc/self/cgroup."""
        mock_cgroup_content = """12:cpuset:/docker/abc123
11:memory:/docker/abc123
10:devices:/docker/abc123"""

        mock_file = mock_open(read_data=mock_cgroup_content)
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "open", mock_file),
        ):
            result = detect_container_environment()
            assert result == "docker"

    def test_detects_podman_via_cgroup(self):
        """Test detection of Podman via /proc/self/cgroup."""
        mock_cgroup_content = """12:cpuset:/podman/xyz789
11:memory:/podman/xyz789"""

        mock_file = mock_open(read_data=mock_cgroup_content)
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "open", mock_file),
        ):
            result = detect_container_environment()
            assert result == "podman"

    def test_detects_podman_via_env_var(self):
        """Test detection of Podman via container environment variable."""
        with (
            patch.object(Path, "exists", return_value=False),
            patch("builtins.open", side_effect=FileNotFoundError),
            patch("os.getenv", return_value="podman"),
        ):
            result = detect_container_environment()
            assert result == "podman"

    def test_returns_none_when_not_in_container(self):
        """Test returns None when not running in a container."""
        mock_cgroup_content = """12:cpuset:/
11:memory:/"""

        mock_file = mock_open(read_data=mock_cgroup_content)
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "open", mock_file),
            patch("os.getenv", return_value=None),
        ):
            result = detect_container_environment()
            assert result is None

    def test_handles_missing_cgroup_file(self):
        """Test gracefully handles missing /proc/self/cgroup file."""
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "open", side_effect=FileNotFoundError),
            patch("os.getenv", return_value=None),
        ):
            result = detect_container_environment()
            assert result is None

    def test_handles_permission_error_on_cgroup(self):
        """Test gracefully handles permission error on /proc/self/cgroup."""
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "open", side_effect=PermissionError),
            patch("os.getenv", return_value=None),
        ):
            result = detect_container_environment()
            assert result is None


class TestGetContainerHost:
    """Test the get_container_host function."""

    def test_returns_none_when_not_in_container(self):
        """Test returns None when not in a container."""
        with patch("lfx.utils.util.detect_container_environment", return_value=None):
            result = get_container_host()
            assert result is None

    def test_returns_docker_internal_when_resolvable(self):
        """Test returns host.docker.internal when it resolves (Docker Desktop)."""
        with (
            patch("lfx.utils.util.detect_container_environment", return_value="docker"),
            patch("socket.getaddrinfo") as mock_getaddrinfo,
        ):
            # First call succeeds (host.docker.internal resolves)
            mock_getaddrinfo.return_value = [("dummy", "data")]

            result = get_container_host()
            assert result == "host.docker.internal"
            mock_getaddrinfo.assert_called_once_with("host.docker.internal", None)

    def test_returns_containers_internal_when_docker_internal_fails(self):
        """Test returns host.containers.internal when host.docker.internal doesn't resolve."""
        with (
            patch("lfx.utils.util.detect_container_environment", return_value="podman"),
            patch("socket.getaddrinfo") as mock_getaddrinfo,
        ):
            # First call fails (host.docker.internal doesn't resolve)
            # Second call succeeds (host.containers.internal resolves)
            def side_effect(hostname, _port):
                msg = "Name or service not known"
                if hostname == "host.docker.internal":
                    raise socket.gaierror(msg)
                return [("dummy", "data")]

            mock_getaddrinfo.side_effect = side_effect

            result = get_container_host()
            assert result == "host.containers.internal"

    def test_returns_gateway_ip_when_no_special_hosts_resolve(self):
        """Test returns gateway IP from routing table when special hostnames don't resolve (Linux)."""
        # Mock routing table with gateway 172.17.0.1
        # Gateway hex 0111A8C0 = 01 11 A8 C0 in little-endian = C0.A8.11.01 = 192.168.17.1
        # Format: Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT
        mock_route_content = """Iface	Destination	Gateway 	Flags	RefCnt	Use	Metric	Mask		MTU	Window	IRTT
eth0	00000000	0111A8C0	0003	0	0	0	00000000	0	0	0
eth0	0011A8C0	00000000	0001	0	0	0	00FFFFFF	0	0	0"""

        mock_file = mock_open(read_data=mock_route_content)
        with (
            patch("lfx.utils.util.detect_container_environment", return_value="docker"),
            patch("socket.getaddrinfo", side_effect=socket.gaierror),
            patch.object(Path, "open", mock_file),
        ):
            result = get_container_host()
            # 0111A8C0 reversed in pairs: C0.A8.11.01 = 192.168.17.1
            assert result == "192.168.17.1"

    def test_returns_none_when_all_methods_fail(self):
        """Test returns None when all detection methods fail."""
        with (
            patch("lfx.utils.util.detect_container_environment", return_value="docker"),
            patch("socket.getaddrinfo", side_effect=socket.gaierror),
            patch.object(Path, "open", side_effect=FileNotFoundError),
        ):
            result = get_container_host()
            assert result is None

    def test_handles_malformed_routing_table(self):
        """Test gracefully handles malformed routing table."""
        mock_route_content = """invalid data here"""

        mock_file = mock_open(read_data=mock_route_content)
        with (
            patch("lfx.utils.util.detect_container_environment", return_value="docker"),
            patch("socket.getaddrinfo", side_effect=socket.gaierror),
            patch.object(Path, "open", mock_file),
        ):
            result = get_container_host()
            assert result is None


class TestTransformLocalhostUrl:
    """Test the transform_localhost_url function."""

    def test_returns_original_url_when_not_in_container(self):
        """Test returns original URL when not in a container."""
        with patch("lfx.utils.util.get_container_host", return_value=None):
            url = "http://localhost:5001/api"
            result = transform_localhost_url(url)
            assert result == url

    def test_transforms_localhost_to_docker_internal(self):
        """Test transforms localhost to host.docker.internal in Docker."""
        with patch("lfx.utils.util.get_container_host", return_value="host.docker.internal"):
            url = "http://localhost:5001/api"
            result = transform_localhost_url(url)
            assert result == "http://host.docker.internal:5001/api"

    def test_transforms_127001_to_docker_internal(self):
        """Test transforms 127.0.0.1 to host.docker.internal in Docker."""
        with patch("lfx.utils.util.get_container_host", return_value="host.docker.internal"):
            url = "http://127.0.0.1:5001/api"
            result = transform_localhost_url(url)
            assert result == "http://host.docker.internal:5001/api"

    def test_transforms_localhost_to_containers_internal(self):
        """Test transforms localhost to host.containers.internal in Podman."""
        with patch("lfx.utils.util.get_container_host", return_value="host.containers.internal"):
            url = "http://localhost:5001/api"
            result = transform_localhost_url(url)
            assert result == "http://host.containers.internal:5001/api"

    def test_transforms_127001_to_containers_internal(self):
        """Test transforms 127.0.0.1 to host.containers.internal in Podman."""
        with patch("lfx.utils.util.get_container_host", return_value="host.containers.internal"):
            url = "http://127.0.0.1:5001/api"
            result = transform_localhost_url(url)
            assert result == "http://host.containers.internal:5001/api"

    def test_transforms_localhost_to_gateway_ip_on_linux(self):
        """Test transforms localhost to gateway IP on Linux containers."""
        with patch("lfx.utils.util.get_container_host", return_value="172.17.0.1"):
            url = "http://localhost:5001/api"
            result = transform_localhost_url(url)
            assert result == "http://172.17.0.1:5001/api"

    def test_transforms_127001_to_gateway_ip_on_linux(self):
        """Test transforms 127.0.0.1 to gateway IP on Linux containers."""
        with patch("lfx.utils.util.get_container_host", return_value="172.17.0.1"):
            url = "http://127.0.0.1:5001/api"
            result = transform_localhost_url(url)
            assert result == "http://172.17.0.1:5001/api"

    def test_does_not_transform_non_localhost_urls(self):
        """Test does not transform URLs that don't contain localhost or 127.0.0.1."""
        with patch("lfx.utils.util.get_container_host", return_value="host.docker.internal"):
            url = "http://example.com:5001/api"
            result = transform_localhost_url(url)
            assert result == url

    def test_transforms_url_without_path(self):
        """Test transforms URL without path."""
        with patch("lfx.utils.util.get_container_host", return_value="host.docker.internal"):
            url = "http://localhost:5001"
            result = transform_localhost_url(url)
            assert result == "http://host.docker.internal:5001"

    def test_transforms_url_with_complex_path(self):
        """Test transforms URL with complex path and query parameters."""
        with patch("lfx.utils.util.get_container_host", return_value="host.docker.internal"):
            url = "http://localhost:5001/api/v1/convert?format=json&timeout=30"
            result = transform_localhost_url(url)
            assert result == "http://host.docker.internal:5001/api/v1/convert?format=json&timeout=30"

    def test_transforms_https_url(self):
        """Test transforms HTTPS URLs."""
        with patch("lfx.utils.util.get_container_host", return_value="host.docker.internal"):
            url = "https://localhost:5001/api"
            result = transform_localhost_url(url)
            assert result == "https://host.docker.internal:5001/api"

    def test_transforms_url_without_port(self):
        """Test transforms URL without explicit port."""
        with patch("lfx.utils.util.get_container_host", return_value="host.docker.internal"):
            url = "http://localhost/api"
            result = transform_localhost_url(url)
            assert result == "http://host.docker.internal/api"

    def test_handles_none_url_gracefully(self):
        """Test returns None when URL is None without raising TypeError."""
        with patch("lfx.utils.util.get_container_host", return_value="host.docker.internal"):
            result = transform_localhost_url(None)
            assert result is None

    def test_handles_empty_string_url_gracefully(self):
        """Test returns empty string when URL is empty string."""
        with patch("lfx.utils.util.get_container_host", return_value="host.docker.internal"):
            result = transform_localhost_url("")
            assert result == ""

    def test_handles_none_url_when_not_in_container(self):
        """Test returns None when URL is None and not in a container."""
        with patch("lfx.utils.util.get_container_host", return_value=None):
            result = transform_localhost_url(None)
            assert result is None

    def test_handles_empty_string_url_when_not_in_container(self):
        """Test returns empty string when URL is empty and not in a container."""
        with patch("lfx.utils.util.get_container_host", return_value=None):
            result = transform_localhost_url("")
            assert result == ""
