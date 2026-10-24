"""Client MCP config files are UTF-8 on disk; decode them as UTF-8."""

import io
import json
from pathlib import Path

import pytest
from langflow.api.v1.mcp_projects import load_client_mcp_config


@pytest.fixture
def ascii_default_encoding(monkeypatch):
    """Make a bare ``Path.open("r")`` decode as ASCII, reproducing a legacy host.

    The client apps (Cursor, Windsurf, Claude Desktop) write their MCP config
    files as UTF-8, and users hand-edit them, so the files regularly contain
    non-ASCII server names or env values. ``Path.open`` resolves a missing
    encoding through ``io.text_encoding(None)``, so the default is forced here
    by patching that entry point: a read that passes no ``encoding`` decodes as
    ASCII and raises on the non-ASCII bytes, while an explicit ``encoding=``
    passes through untouched. That keeps the test red against a bare read on
    any host, including CI's UTF-8 Linux (where this repo's interpreter runs
    with UTF-8 mode on and the locale alone would never fail).
    """
    real_text_encoding = io.text_encoding

    def _forced(encoding=None, stacklevel=1):
        if encoding is None:
            return "ascii"
        return real_text_encoding(encoding, stacklevel)

    monkeypatch.setattr(io, "text_encoding", _forced, raising=True)


def _write_client_config(path: Path) -> None:
    """A client-shaped config whose server name and env value hold non-ASCII."""
    path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "我的服务": {"command": "npx", "env": {"NOTE": "中文备注"}},
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


@pytest.mark.usefixtures("ascii_default_encoding")
def test_load_client_mcp_config_decodes_utf8_regardless_of_locale(tmp_path: Path) -> None:
    config_path = tmp_path / "mcp.json"
    _write_client_config(config_path)

    config = load_client_mcp_config(config_path)

    assert "我的服务" in config["mcpServers"]
    assert config["mcpServers"]["我的服务"]["env"]["NOTE"] == "中文备注"


@pytest.mark.usefixtures("ascii_default_encoding")
def test_load_client_mcp_config_still_raises_jsondecodeerror_for_invalid_json(
    tmp_path: Path,
) -> None:
    """Invalid JSON still surfaces as JSONDecodeError, the call sites' catch."""
    config_path = tmp_path / "mcp.json"
    config_path.write_bytes(b"{not json}")

    with pytest.raises(json.JSONDecodeError):
        load_client_mcp_config(config_path)
