"""JWT authentication regressions shared by both OpenSearch components."""

from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("lfx_bundles")

from lfx_bundles.elastic.opensearch import OpenSearchVectorStoreComponent
from lfx_bundles.elastic.opensearch_multimodal import OpenSearchVectorStoreComponentMultimodalMultiEmbedding
from pydantic import SecretStr

_TEST_JWT = "header.payload.signature"  # pragma: allowlist secret
_COMPONENT_CLASSES = (
    pytest.param(OpenSearchVectorStoreComponent, id="opensearch"),
    pytest.param(OpenSearchVectorStoreComponentMultimodalMultiEmbedding, id="opensearch-multimodal"),
)


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
def test_jwt_token_default_is_preserved(component_class: type[Any]) -> None:
    jwt_input = next(input_ for input_ in component_class().inputs if input_.name == "jwt_token")

    assert jwt_input.value == "JWT"
    assert jwt_input.load_from_db is False


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
def test_jwt_auth_without_token_raises(component_class: type[Any]) -> None:
    component = component_class()
    component.set_attributes({"auth_mode": "jwt", "jwt_token": ""})

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


@pytest.mark.parametrize("engine", ["jvector", "nmslib", "faiss", "lucene"])
@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
def test_opensearch_mapping_uses_method_supported_by_engine(component_class, engine):
    component = component_class()
    mapping = component._default_text_mapping(dim=3, engine=engine)
    method = mapping["mappings"]["properties"]["vector_field"]["method"]

    assert method["engine"] == engine
    assert method["name"] == ("disk_ann" if engine == "jvector" else "hnsw")


@pytest.mark.parametrize("engine", ["jvector", "nmslib", "faiss", "lucene"])
def test_multimodal_dynamic_mapping_uses_method_supported_by_engine(engine):
    component = OpenSearchVectorStoreComponentMultimodalMultiEmbedding()
    client = MagicMock()
    client.indices.get_mapping.side_effect = [
        {component.index_name: {"mappings": {"properties": {}}}},
        {component.index_name: {"mappings": {"properties": {"embedding": {"type": "knn_vector", "dimension": 3}}}}},
    ]

    component._ensure_embedding_field_mapping(
        client=client,
        index_name=component.index_name,
        field_name="embedding",
        dim=3,
        engine=engine,
        space_type="l2",
        ef_construction=100,
        m=16,
    )

    method = client.indices.put_mapping.call_args.kwargs["body"]["properties"]["embedding"]["method"]
    assert method["engine"] == engine
    assert method["name"] == ("disk_ann" if engine == "jvector" else "hnsw")
