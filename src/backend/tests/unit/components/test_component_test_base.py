"""Tests for the ComponentTestBase harness itself.

test_latest_version once passed for every component without running a single output
method. These tests pin down what it must catch, so it cannot quietly go vacuous again.
"""

import socket

import pytest
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient, _is_local_address

# TEST-NET-1 (RFC 5737): reserved for documentation, never routed.
UNROUTABLE_ADDRESS = ("192.0.2.1", 80)


class _EchoComponent(Component):
    display_name = "Echo"
    inputs = [MessageTextInput(name="text", display_name="Text")]
    outputs = [Output(display_name="Echo", name="echo", method="echo")]

    def echo(self) -> Message:
        return Message(text=self.text)


class _NoneComponent(Component):
    display_name = "None"
    outputs = [
        Output(display_name="Echo", name="echo", method="echo"),
        Output(display_name="Nothing", name="nothing", method="nothing"),
    ]

    def echo(self) -> Message:
        return Message(text="value")

    def nothing(self) -> Message:
        return None


class _NetworkComponent(Component):
    """Swallows the connection error and falls back, as many real components do."""

    display_name = "Network"
    outputs = [
        Output(display_name="Echo", name="echo", method="echo"),
        Output(display_name="Fetched", name="fetched", method="fetch"),
    ]

    def echo(self) -> Message:
        return Message(text="value")

    def fetch(self) -> Message:
        try:
            with socket.create_connection(UNROUTABLE_ADDRESS, timeout=1):
                return Message(text="online")
        except OSError:
            return Message(text="offline fallback")


class _NoOutputsComponent(Component):
    display_name = "No outputs"
    outputs = []


@pytest.fixture
def harness():
    return ComponentTestBaseWithoutClient()


async def test_passes_when_every_output_returns_a_value(harness):
    await harness.test_latest_version(_EchoComponent, {"text": "hi"}, {})


async def test_fails_when_an_output_returns_none(harness):
    with pytest.raises(AssertionError, match=r"returned None: \['nothing'\]"):
        await harness.test_latest_version(_NoneComponent, {}, {})


async def test_fails_when_an_output_reaches_the_network_even_if_it_falls_back(harness):
    with pytest.raises(AssertionError, match=r"tried to reach the network: \[\"fetched -> \('192\.0\.2\.1', 80\)"):
        await harness.test_latest_version(_NetworkComponent, {}, {})


async def test_does_not_run_skipped_outputs(harness):
    await harness.test_latest_version(_NetworkComponent, {}, {"fetched": "needs the network"})


async def test_skips_when_every_output_is_skipped(harness):
    with pytest.raises(pytest.skip.Exception, match="Every output of _NetworkComponent is in skipped_outputs"):
        await harness.test_latest_version(
            _NetworkComponent, {}, {"echo": "for the test", "fetched": "needs the network"}
        )


async def test_rejects_skipped_outputs_the_component_does_not_have(harness):
    with pytest.raises(AssertionError, match=r"does not have: \['renamed'\]"):
        await harness.test_latest_version(_EchoComponent, {"text": "hi"}, {"renamed": "stale entry"})


async def test_fails_when_the_component_has_no_outputs(harness):
    with pytest.raises(AssertionError, match="has no outputs to run"):
        await harness.test_latest_version(_NoOutputsComponent, {}, {})


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        (("127.0.0.1", 80), True),
        (("::1", 80, 0, 0), True),
        (("localhost", 80), True),
        ("/tmp/app.sock", True),  # noqa: S108 - a Unix socket path, never opened
        (UNROUTABLE_ADDRESS, False),
        (("api.openai.com", 443), False),
    ],
)
def test_only_loopback_and_unix_sockets_count_as_local(address, expected):
    assert _is_local_address(address) is expected
