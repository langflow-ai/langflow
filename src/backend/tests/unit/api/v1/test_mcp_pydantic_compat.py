from unittest.mock import MagicMock

import pydantic
import pytest
from langflow.api.v1.mcp import _ensure_mcp_root_model_ready, _ensure_mcp_root_models_ready
from mcp import types
from pydantic_core import PydanticUndefined


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


@pytest.mark.parametrize(
    ("request_model", "method"),
    [
        (types.ListPromptsRequest, "prompts/list"),
        (types.ListResourceTemplatesRequest, "resources/templates/list"),
        (types.ListResourcesRequest, "resources/list"),
        (types.ListTasksRequest, "tasks/list"),
        (types.ListToolsRequest, "tools/list"),
    ],
)
def test_missing_paginated_request_default_is_restored(request_model, method):
    params_field = request_model.model_fields["params"]
    original_default = params_field.default

    try:
        params_field.default = PydanticUndefined
        request_model.model_rebuild(force=True)
        types.ClientRequest.model_rebuild(
            force=True,
            _types_namespace={"RootModelRootType": types.ClientRequestType},
        )
        wire_request = request_model(params=None).model_dump(by_alias=True, mode="json", exclude_none=True)
        assert wire_request == {"method": method}

        with pytest.raises(pydantic.ValidationError, match="params"):
            types.ClientRequest.model_validate(wire_request)

        _ensure_mcp_root_models_ready()

        request = types.ClientRequest.model_validate(wire_request)
        assert isinstance(request.root, request_model)
        assert request.root.params is None
    finally:
        params_field.default = original_default
        request_model.model_rebuild(force=True)
        types.ClientRequest.model_rebuild(
            force=True,
            _types_namespace={"RootModelRootType": types.ClientRequestType},
        )
