"""JWT authentication regressions shared by both OpenSearch components."""

from typing import Any

import pytest
from lfx_bundles.elastic.opensearch import OpenSearchVectorStoreComponent
from lfx_bundles.elastic.opensearch_multimodal import OpenSearchVectorStoreComponentMultimodalMultiEmbedding
from pydantic import SecretStr

_TEST_JWT = "header.payload.signature"  # pragma: allowlist secret
_COMPONENT_CLASSES = (
    pytest.param(OpenSearchVectorStoreComponent, id="opensearch"),
    pytest.param(OpenSearchVectorStoreComponentMultimodalMultiEmbedding, id="opensearch-multimodal"),
)


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
def test_jwt_token_default_is_blank(component_class: type[Any]) -> None:
    jwt_input = next(input_ for input_ in component_class().inputs if input_.name == "jwt_token")

    assert jwt_input.value == ""
    assert jwt_input.load_from_db is False


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
def test_jwt_auth_without_token_raises(component_class: type[Any]) -> None:
    component = component_class()
    component.set_attributes({"auth_mode": "jwt"})

    with pytest.raises(ValueError, match="no jwt_token was provided"):
        component._build_auth_kwargs()


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
async def test_jwt_global_named_like_old_default_survives_refresh(component_class: type[Any]) -> None:
    component = component_class()
    fresh_node = component.to_frontend_node()["data"]["node"]
    saved_node = component_class().to_frontend_node()["data"]["node"]
    saved_node["template"]["jwt_token"].update(value="JWT", load_from_db=True)

    refreshed = await component.update_frontend_node(fresh_node, saved_node)

    assert refreshed["template"]["jwt_token"]["value"] == "JWT"
    assert refreshed["template"]["jwt_token"]["load_from_db"] is True


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
@pytest.mark.parametrize(
    "runtime_token",
    [_TEST_JWT, SecretStr(_TEST_JWT)],
    ids=["literal", "credential-global"],
)
@pytest.mark.parametrize("bearer_prefix", [False, True], ids=["raw", "bearer"])
def test_jwt_auth_header(
    component_class: type[Any],
    runtime_token: str | SecretStr,
    *,
    bearer_prefix: bool,
) -> None:
    component = component_class()
    component.set_attributes(
        {
            "auth_mode": "jwt",
            "jwt_token": runtime_token,
            "jwt_header": "Authorization",
            "bearer_prefix": bearer_prefix,
        }
    )

    expected = f"Bearer {_TEST_JWT}" if bearer_prefix else _TEST_JWT
    assert component._build_auth_kwargs() == {"headers": {"Authorization": expected}}
