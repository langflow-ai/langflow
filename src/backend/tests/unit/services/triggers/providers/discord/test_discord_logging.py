"""The installed WebSocket protocol must not log credentials or private frames."""

import os
import subprocess
import sys


def test_real_protocol_debug_logging_is_suppressed_for_discord():
    code = """
import io
import json
import logging
from websockets.client import ClientProtocol
from websockets.frames import Frame, OP_TEXT
from websockets.protocol import State
from websockets.uri import parse_uri
from langflow.services.triggers.providers.discord.gateway import _WEBSOCKET_LOGGER

stream = io.StringIO()
handler = logging.StreamHandler(stream)
root = logging.getLogger()
root.setLevel(logging.DEBUG)
root.addHandler(handler)
logging.getLogger("websockets.client").setLevel(logging.DEBUG)
marker = "synthetic-protocol-credential-" + "x" * 100
private = "synthetic-private-guild-message"

def exercise(logger=None):
    protocol = ClientProtocol(parse_uri("wss://gateway.discord.gg/"), state=State.OPEN, logger=logger)
    protocol.send_text(json.dumps({"op": 2, "d": {"token": marker}}).encode())
    protocol.send_text(json.dumps({"op": 6, "d": {"token": marker, "session_id": "fixture", "seq": 1}}).encode())
    inbound = Frame(OP_TEXT, json.dumps({"op": 0, "d": {"content": private}}).encode())
    protocol.receive_data(inbound.serialize(mask=False))

exercise()
control = stream.getvalue()
assert marker in control and private in control
stream.seek(0)
stream.truncate(0)
exercise(_WEBSOCKET_LOGGER)
safe = stream.getvalue()
assert marker not in safe and private not in safe
assert "> TEXT" not in safe and "< TEXT" not in safe
print("Real installed protocol logging regression passed.")
"""
    result = subprocess.run(  # noqa: S603 - trusted literal code and current interpreter
        [sys.executable, "-c", code],
        env={**os.environ, "LANGFLOW_LOG_LEVEL": "DEBUG", "WEBSOCKETS_MAX_LOG_SIZE": "4096"},
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "Real installed protocol logging regression passed." in result.stdout
