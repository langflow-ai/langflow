"""Exercise exported provider actions through a fresh headless CLI process."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import lfx_discord
import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx_discord import DiscordSendMessageComponent


@pytest.mark.parametrize("source", ["json", "python"])
def test_cli_supports_discord_without_preloaded_registry(tmp_path, source):
    chat = ChatInput(_id="chat").set(input_value="hello")
    action = DiscordSendMessageComponent(
        _id="discord", connection="discord/work", guild_id="123456789012345678", channel_id="234567890123456789"
    ).set(text=chat.message_response)
    output = ChatOutput(_id="output").set(input_value=action.build_message)
    exported = Graph(start=chat, end=output).dump()
    for node in exported["data"]["nodes"]:
        code = node["data"]["node"]["template"]["code"]
        code["value"] = code["value"].splitlines()
    path = tmp_path / "discord.json"
    path.write_text(json.dumps(exported), encoding="utf-8")
    if source == "python":
        path = tmp_path / "discord.py"
        path.write_text(
            "from lfx.graph import Graph\n"
            "from lfx.components.input_output import ChatInput, ChatOutput\n"
            "from lfx_discord import DiscordSendMessageComponent\n"
            "chat = ChatInput(_id='chat').set(input_value='hello')\n"
            'action = DiscordSendMessageComponent(_id="discord", connection="discord/work", '
            'guild_id="123456789012345678", channel_id="234567890123456789").set(text=chat.message_response)\n'
            "output = ChatOutput(_id='output').set(input_value=action.build_message)\n"
            "graph = Graph(start=chat, end=output)\n",
            encoding="utf-8",
        )
    env = os.environ.copy()
    env["LANGFLOW_ALLOW_CUSTOM_COMPONENTS"] = "true"
    # Exercise source bundle discovery without preloading or mocking its registry.
    env["LANGFLOW_SEED_DIR"] = str(Path(lfx_discord.__file__).parent.parent)
    env["DO_NOT_TRACK"] = "1"
    # Missing credentials bound the test before any provider network request.
    env.pop("LF_CONNECTION__DISCORD__WORK", None)

    result = subprocess.run(  # noqa: S603 - fixed CLI arguments and a test-generated flow
        [
            sys.executable,
            "-m",
            "lfx",
            "run",
            str(path),
            "--input-value",
            "hello",
            "--check-variables",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 1
    response = json.loads(result.stdout)
    assert response["exception_type"] == "ConnectionUnresolvedError"
    assert "LF_CONNECTION__DISCORD__WORK" in response["exception_message"]
    assert "not available in headless" not in response["exception_message"]
    assert "Traceback" not in result.stdout + result.stderr
