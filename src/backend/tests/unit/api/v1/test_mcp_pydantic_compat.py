from unittest.mock import MagicMock

from langflow.api.v1.mcp import _ensure_mcp_root_model_ready, _ensure_mcp_root_models_ready
from mcp import types


def test_complete_mcp_root_model_is_not_rebuilt():
    model = MagicMock()
    model.__pydantic_complete__ = True

    _ensure_mcp_root_model_ready(model, object())

    model.model_rebuild.assert_not_called()


def test_incomplete_mcp_root_model_is_rebuilt_with_explicit_root_type():
    model = MagicMock()
    model.__pydantic_complete__ = False
    root_type = object()

    _ensure_mcp_root_model_ready(model, root_type)

    model.model_rebuild.assert_called_once_with(_types_namespace={"RootModelRootType": root_type})


def test_ready_mcp_root_models_remain_unchanged():
    root_models = (
        types.JSONRPCMessage,
        types.ClientRequest,
        types.ClientNotification,
        types.ClientResult,
        types.ServerRequest,
        types.ServerNotification,
        types.ServerResult,
    )
    validators = [model.__pydantic_validator__ for model in root_models]

    _ensure_mcp_root_models_ready()

    assert all(model.__pydantic_complete__ for model in root_models)
    assert all(
        model.__pydantic_validator__ is validator for model, validator in zip(root_models, validators, strict=True)
    )
