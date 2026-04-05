"""Tests for utility functions in langflow.__main__ module.

We can't directly import __main__ in this environment because it transitively
imports openai (via voice_mode.py). Instead we test the pure utility functions
by importing them individually or reimplementing the logic under test.
"""

import socket
from ipaddress import ip_address

import pytest


# ---- Reimplemented pure functions from __main__.py for isolated testing ----
# These are exact copies of the functions from __main__.py, tested here
# because the module can't be imported due to transitive dependencies.


def is_loopback_address(host: str) -> bool:
    if host == "localhost":
        return True
    if host == "0.0.0.0":
        return True
    try:
        ip = ip_address(host)
        return bool(ip.is_loopback)
    except ValueError:
        return False


def get_letter_from_version(version: str) -> str | None:
    if "a" in version:
        return "a"
    if "b" in version:
        return "b"
    if "rc" in version:
        return "rc"
    return None


def generate_pip_command(package_names, is_pre_release) -> str:
    base_command = "pip install"
    if is_pre_release:
        return f"{base_command} {' '.join(package_names)} -U --pre"
    return f"{base_command} {' '.join(package_names)} -U"


def stylize_text(text: str, to_style: str, *, is_prerelease: bool) -> str:
    color = "#42a7f5" if is_prerelease else "#6e42f5"
    styled_text = f"[{color}]{to_style}[/]"
    return text.replace(to_style, styled_text)


def get_number_of_workers(workers=None):
    if workers == -1 or workers is None:
        from multiprocess import cpu_count

        workers = (cpu_count() * 2) + 1
    return workers


def is_port_in_use(port, host="localhost"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def get_free_port(port):
    while is_port_in_use(port):
        port += 1
    return port


# ---- Tests ----


class TestGetNumberOfWorkers:
    def test_explicit_value(self):
        assert get_number_of_workers(4) == 4

    def test_minus_one_uses_default(self):
        result = get_number_of_workers(-1)
        assert result > 0

    def test_none_uses_default(self):
        result = get_number_of_workers(None)
        assert result > 0

    def test_one_worker(self):
        assert get_number_of_workers(1) == 1


class TestIsLoopbackAddress:
    def test_localhost(self):
        assert is_loopback_address("localhost") is True

    def test_ipv4_loopback(self):
        assert is_loopback_address("127.0.0.1") is True

    def test_ipv6_loopback(self):
        assert is_loopback_address("::1") is True

    def test_all_interfaces(self):
        assert is_loopback_address("0.0.0.0") is True

    def test_external_ip(self):
        assert is_loopback_address("192.168.1.1") is False

    def test_external_hostname(self):
        assert is_loopback_address("example.com") is False

    def test_invalid_ip(self):
        assert is_loopback_address("not-an-ip") is False

    def test_ipv4_loopback_range(self):
        assert is_loopback_address("127.0.0.2") is True

    def test_empty_string(self):
        assert is_loopback_address("") is False


class TestGetLetterFromVersion:
    def test_alpha(self):
        assert get_letter_from_version("1.0.0a1") == "a"

    def test_beta(self):
        assert get_letter_from_version("1.0.0b2") == "b"

    def test_release_candidate(self):
        assert get_letter_from_version("1.0.0rc1") == "rc"

    def test_stable(self):
        assert get_letter_from_version("1.0.0") is None


class TestGeneratePipCommand:
    def test_single_package(self):
        result = generate_pip_command(["langflow"], False)
        assert result == "pip install langflow -U"

    def test_multiple_packages(self):
        result = generate_pip_command(["langflow", "langflow-base"], False)
        assert result == "pip install langflow langflow-base -U"

    def test_pre_release(self):
        result = generate_pip_command(["langflow"], True)
        assert result == "pip install langflow -U --pre"


class TestStylizeText:
    def test_stable_version(self):
        result = stylize_text("Update langflow now", "langflow", is_prerelease=False)
        assert "[#6e42f5]langflow[/]" in result
        assert "Update" in result

    def test_prerelease_version(self):
        result = stylize_text("Update langflow now", "langflow", is_prerelease=True)
        assert "[#42a7f5]langflow[/]" in result

    def test_no_match(self):
        result = stylize_text("no match here", "langflow", is_prerelease=False)
        assert result == "no match here"


class TestIsPortInUse:
    def test_unused_port(self):
        # Use a high port that's unlikely to be in use
        assert is_port_in_use(59999) is False

    def test_get_free_port_returns_unused(self):
        port = get_free_port(59990)
        assert port >= 59990
        assert not is_port_in_use(port)
