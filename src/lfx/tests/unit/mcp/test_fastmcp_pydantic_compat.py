from unittest.mock import MagicMock

from lfx.base.mcp.pydantic_compat import (
    _ensure_fastmcp_settings_model_ready,
    ensure_fastmcp_settings_ready,
)
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import Settings


def test_complete_fastmcp_settings_model_is_not_rebuilt() -> None:
    model = MagicMock()
    model.__pydantic_complete__ = True

    _ensure_fastmcp_settings_model_ready(model, FastMCP)

    model.model_rebuild.assert_not_called()


def test_incomplete_fastmcp_settings_model_is_rebuilt_with_explicit_type() -> None:
    model = MagicMock()
    model.__pydantic_complete__ = False

    _ensure_fastmcp_settings_model_ready(model, FastMCP)

    model.model_rebuild.assert_called_once_with(_types_namespace={"FastMCP": FastMCP})


def test_installed_fastmcp_settings_model_is_ready_before_construction() -> None:
    ensure_fastmcp_settings_ready()

    assert Settings.__pydantic_complete__
    assert FastMCP("compatibility-test").settings is not None
