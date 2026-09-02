import gzip
import json

import pytest
from langflow.services.database.models.flow_version.exceptions import FlowVersionSerializationError
from langflow.services.database.models.flow_version.serialization import pack, unpack
from sqlalchemy import Integer

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


def test_the_column_stores_gzip_bytes_and_reads_back_a_dict():
    from langflow.services.database.models.flow_version.serialization import GzippedJSON
    from sqlalchemy import Column, MetaData, Table, create_engine, select

    metadata = MetaData()
    table = Table("sample", metadata, Column("id", Integer, primary_key=True), Column("payload", GzippedJSON))
    engine = create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(table.insert().values(id=1, payload=GRAPH))
        conn.execute(table.insert().values(id=2, payload=None))

    with engine.connect() as conn:
        assert conn.execute(select(table.c.payload).where(table.c.id == 1)).scalar_one() == GRAPH
        assert conn.execute(select(table.c.payload).where(table.c.id == 2)).scalar_one() is None
        raw = conn.exec_driver_sql("SELECT payload FROM sample WHERE id = 1").scalar_one()

    assert raw[:2] == b"\x1f\x8b"
    assert b"lfx" not in raw
