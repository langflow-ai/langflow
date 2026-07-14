"""Tests for the embedded Agent chat-history ownership migration."""

import hashlib
import importlib
import types

import sqlalchemy as sa

_MIGRATION = importlib.import_module("langflow.alembic.versions.90c977dcf0f1_scope_embedded_agent_chat_history")

_IMPORT = "from lfx.components.models_and_agents.memory import MemoryComponent, aget_agent_chat_history\n"
_OLD_METHOD = (
    "    async def get_memory_data(self):\n"
    '        # Scope by flow_id so default playground session names (e.g. "New Session 0")\n'
    "        # cannot leak chat history across unrelated flows. See issue #13059.\n"
    "        # The helper also returns [] when n_messages == 0, preserving the\n"
    '        # explicit "memory disabled" contract from MemoryComponent.retrieve_messages.\n'
    "        messages = await aget_agent_chat_history(\n"
    "            session_id=self.graph.session_id,\n"
    '            flow_id=getattr(self.graph, "flow_id", None),\n'
    "            context_id=self.context_id,\n"
    "            n_messages=self.n_messages,\n"
    "        )\n"
    "        return [\n"
    '            message for message in messages if getattr(message, "id", None) '
    '!= getattr(self.input_value, "id", None)\n'
    "        ]\n"
)


def _flow_data(code: str) -> dict:
    return {
        "nodes": [
            {
                "data": {
                    "type": "Agent",
                    "node": {
                        "template": {"code": {"value": code}},
                        "metadata": {"code_hash": "deadbeef0000"},
                    },
                }
            }
        ],
        "edges": [],
    }


def test_rewrite_adds_user_scope_and_rehashes_agent_snapshot():
    code = f"{_IMPORT}\nclass AgentComponent:\n{_OLD_METHOD}"
    data = _flow_data(code)

    assert _MIGRATION._rewrite_flow_data(data)
    node = data["nodes"][0]["data"]["node"]
    rewritten = node["template"]["code"]["value"]
    assert "user_id=_safe_graph_user_id(self)" in rewritten
    assert "MemoryComponent, _safe_graph_user_id, aget_agent_chat_history" in rewritten
    assert node["metadata"]["code_hash"] == hashlib.sha256(rewritten.encode()).hexdigest()[:12]
    assert not _MIGRATION._rewrite_flow_data(data)


def test_upgrade_rewrites_stored_flow_rows():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    flow = sa.Table(
        "flow",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("data", sa.JSON()),
    )
    metadata.create_all(engine)
    code = f"{_IMPORT}\nclass AgentComponent:\n{_OLD_METHOD}"
    with engine.begin() as conn:
        conn.execute(flow.insert(), [{"id": "stale", "data": _flow_data(code)}])
        original_op = _MIGRATION.op
        try:
            _MIGRATION.op = types.SimpleNamespace(get_bind=lambda: conn)
            _MIGRATION.upgrade()
        finally:
            _MIGRATION.op = original_op

    with engine.connect() as conn:
        rewritten = conn.execute(sa.select(flow.c.data)).scalar_one()
    value = rewritten["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    assert "user_id=_safe_graph_user_id(self)" in value
