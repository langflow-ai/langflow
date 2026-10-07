"""k-NN method selection regressions shared by both OpenSearch components (LE-2652, #15094).

``disk_ann`` exists only in the opensearch-jvector plugin. Stock OpenSearch rejects it for the
``nmslib``, ``faiss``, and ``lucene`` engines with ``Invalid method name: disk_ann``, so every
mapping builder must pick the method from the selected engine.
"""

from typing import Any

import pytest

pytest.importorskip("lfx_bundles")

from lfx_bundles.elastic.opensearch import OpenSearchVectorStoreComponent
from lfx_bundles.elastic.opensearch_multimodal import OpenSearchVectorStoreComponentMultimodalMultiEmbedding
from opensearchpy.exceptions import RequestError

_COMPONENT_CLASSES = (
    pytest.param(OpenSearchVectorStoreComponent, id="opensearch"),
    pytest.param(OpenSearchVectorStoreComponentMultimodalMultiEmbedding, id="opensearch-multimodal"),
)
_EXPECTED_METHOD_BY_ENGINE = {"jvector": "disk_ann", "nmslib": "hnsw", "faiss": "hnsw", "lucene": "hnsw"}
_ENGINE_CASES = [pytest.param(engine, method, id=engine) for engine, method in _EXPECTED_METHOD_BY_ENGINE.items()]
_DYNAMIC_FIELD = "chunk_embedding_text_embedding_3_small"


class _MappingRecordingIndices:
    """Minimal ``client.indices`` double that applies ``put_mapping`` bodies to its mapping."""

    def __init__(self, put_mapping_error: Exception | None = None) -> None:
        self.properties: dict[str, Any] = {}
        self.put_mapping_bodies: list[dict[str, Any]] = []
        self._put_mapping_error = put_mapping_error

    def get_mapping(self, index: str) -> dict[str, Any]:
        return {index: {"mappings": {"properties": dict(self.properties)}}}

    def put_mapping(self, index: str, body: dict[str, Any]) -> None:  # noqa: ARG002
        if self._put_mapping_error is not None:
            raise self._put_mapping_error
        self.put_mapping_bodies.append(body)
        self.properties.update(body["properties"])


class _MappingRecordingClient:
    def __init__(self, put_mapping_error: Exception | None = None) -> None:
        self.indices = _MappingRecordingIndices(put_mapping_error)


def _vector_method(mapping: dict[str, Any], field: str = "vector_field") -> dict[str, Any]:
    return mapping["mappings"]["properties"][field]["method"]


def _ensure_dynamic_field(client: _MappingRecordingClient, engine: str) -> None:
    component = OpenSearchVectorStoreComponentMultimodalMultiEmbedding()
    component.set_attributes({"index_name": "documents"})
    component._ensure_embedding_field_mapping(
        client=client,
        index_name="documents",
        field_name=_DYNAMIC_FIELD,
        dim=3,
        engine=engine,
        space_type="l2",
        ef_construction=100,
        m=16,
    )


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
def test_engine_options_are_all_covered(component_class: type[Any]) -> None:
    engine_input = next(input_ for input_ in component_class().inputs if input_.name == "engine")

    assert set(engine_input.options) == set(_EXPECTED_METHOD_BY_ENGINE)


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
@pytest.mark.parametrize(("engine", "expected_method"), _ENGINE_CASES)
def test_index_mapping_uses_method_supported_by_engine(
    component_class: type[Any], engine: str, expected_method: str
) -> None:
    mapping = component_class()._default_text_mapping(
        dim=3,
        engine=engine,
        space_type="cosinesimil",
        ef_construction=512,
        m=16,
        vector_field="chunk_embedding",
    )

    assert _vector_method(mapping, "chunk_embedding") == {
        "name": expected_method,
        "space_type": "cosinesimil",
        "engine": engine,
        "parameters": {"ef_construction": 512, "m": 16},
    }


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
def test_index_mapping_default_engine_keeps_disk_ann(component_class: type[Any]) -> None:
    method = _vector_method(component_class()._default_text_mapping(dim=3))

    assert (method["engine"], method["name"]) == ("jvector", "disk_ann")


@pytest.mark.parametrize("component_class", _COMPONENT_CLASSES)
@pytest.mark.parametrize(
    ("engine", "expected_method"), [("FAISS", "hnsw"), ("Lucene", "hnsw"), ("JVector", "disk_ann")]
)
def test_index_mapping_engine_match_is_case_insensitive(
    component_class: type[Any], engine: str, expected_method: str
) -> None:
    # OpenSearch resolves engine names case-insensitively, so the method must follow suit.
    method = _vector_method(component_class()._default_text_mapping(dim=3, engine=engine))

    assert method["name"] == expected_method


@pytest.mark.parametrize(("engine", "expected_method"), _ENGINE_CASES)
def test_multimodal_dynamic_field_mapping_uses_method_supported_by_engine(engine: str, expected_method: str) -> None:
    client = _MappingRecordingClient()

    _ensure_dynamic_field(client, engine)

    [body] = client.indices.put_mapping_bodies
    assert body["properties"][_DYNAMIC_FIELD]["method"] == {
        "name": expected_method,
        "space_type": "l2",
        "engine": engine,
        "parameters": {"ef_construction": 100, "m": 16},
    }


def test_multimodal_dynamic_field_missing_jvector_plugin_points_to_plugin() -> None:
    # Response body returned by stock OpenSearch (2.19.3, 3.8.0) when the opensearch-jvector plugin is absent.
    reason = "Invalid engine: jvector"
    body = {
        "error": {
            "root_cause": [{"type": "mapper_parsing_exception", "reason": reason}],
            "type": "mapper_parsing_exception",
            "reason": f"Failed to parse mapping [_doc]: {reason}",
        },
        "status": 400,
    }
    client = _MappingRecordingClient(put_mapping_error=RequestError(400, "mapper_parsing_exception", body))

    with pytest.raises(ValueError, match="requires the opensearch-jvector plugin"):
        _ensure_dynamic_field(client, "jvector")
