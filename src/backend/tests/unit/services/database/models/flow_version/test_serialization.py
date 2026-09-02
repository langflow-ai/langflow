import gzip
import json

import pytest
from langflow.services.database.models.flow_version.exceptions import FlowVersionSerializationError
from langflow.services.database.models.flow_version.serialization import pack, unpack

GRAPH = {
    "nodes": [{"id": "node-1", "data": {"node": {"template": {"code": {"value": "from lfx import x\n"}}}}}],
    "edges": [],
    "viewport": {"x": 0, "y": 0, "zoom": 1},
}


def test_pack_then_unpack_returns_an_equal_document():
    assert unpack(pack(GRAPH)) == GRAPH


def test_pack_returns_gzip_bytes():
    packed = pack(GRAPH)

    assert isinstance(packed, bytes)
    assert json.loads(gzip.decompress(packed)) == GRAPH


def test_pack_shrinks_a_repetitive_graph():
    graph = {"nodes": [GRAPH["nodes"][0] for _ in range(50)], "edges": []}

    packed = pack(graph)

    assert len(packed) < len(json.dumps(graph).encode()) / 4


def test_none_passes_through_both_ways():
    assert pack(None) is None
    assert unpack(None) is None


def test_non_ascii_survives_the_round_trip():
    graph = {"nodes": [], "edges": [], "name": "Análise de Sentimento — ação"}

    assert unpack(pack(graph)) == graph


def test_unpack_rejects_data_that_is_not_gzip():
    with pytest.raises(FlowVersionSerializationError):
        unpack(b"not gzip at all")


def test_unpack_rejects_gzip_that_is_not_json():
    with pytest.raises(FlowVersionSerializationError):
        unpack(gzip.compress(b"<html></html>"))


def test_pack_rejects_a_document_json_cannot_encode():
    with pytest.raises(FlowVersionSerializationError):
        pack({"nodes": {object()}})
