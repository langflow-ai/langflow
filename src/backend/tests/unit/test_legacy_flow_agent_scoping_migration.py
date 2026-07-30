"""Tests for the ``b2c72e1e1439`` data migration.

The migration rewrites the embedded ``get_memory_data`` in already-seeded Flow rows so
legacy Agent snapshots read chat history through the user-scoped
``aget_agent_chat_history(..., user_id=_safe_graph_user_id(self))`` path instead of the
unscoped ``MemoryComponent(**self.get_base_args()).retrieve_messages()`` path (CWE-200).

These tests use an in-memory SQLite database and the migration module's own functions —
they deliberately avoid the app ``client``/``session`` fixtures so nothing rewrites the
packaged starter-project/agentic JSON on disk.
"""

import hashlib
import importlib.util
import types
from pathlib import Path

import langflow
import pytest
import sqlalchemy as sa

MIGRATION_ID = "b2c72e1e1439"


@pytest.fixture(scope="module")
def migration():
    """Load the migration module by path (it is not an importable package)."""
    versions = Path(langflow.__file__).parent / "alembic" / "versions"
    matches = list(versions.glob(f"{MIGRATION_ID}_*.py"))
    assert len(matches) == 1, f"expected exactly one migration file, found {matches}"
    spec = importlib.util.spec_from_file_location(f"mig_{MIGRATION_ID}", matches[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# A compact but faithful pre-fix Agent snapshot: the real old memory import plus the exact
# old ``get_memory_data`` body, defined independently of the migration's own constants.
def _stale_agent_code(*, import_line: str) -> str:
    return (
        f"{import_line}\n"
        "\n"
        "class AgentComponent:\n"
        "    memory_inputs = [c for c in MemoryComponent().inputs]\n"
        "\n"
        "    async def get_memory_data(self):\n"
        "        # TODO: This is a temporary fix to avoid message duplication. We should develop a function for this.\n"
        "        messages = (\n"
        "            await MemoryComponent(**self.get_base_args())\n"
        "            .set(\n"
        "                session_id=self.graph.session_id,\n"
        "                context_id=self.context_id,\n"
        '                order="Ascending",\n'
        "                n_messages=self.n_messages,\n"
        "            )\n"
        "            .retrieve_messages()\n"
        "        )\n"
        "        return [\n"
        '            message for message in messages if getattr(message, "id", None) != getattr(self.input_value, "id", None)\n'  # noqa: E501
        "        ]\n"
    )


_MODELS_IMPORT = "from lfx.components.models_and_agents.memory import MemoryComponent"
_HELPERS_IMPORT = "from lfx.components.helpers.memory import MemoryComponent"


def _agent_flow_data(code: str, *, code_hash: str = "0" * 12) -> dict:
    return {
        "nodes": [
            {
                "id": "Agent-abc",
                "data": {
                    "type": "Agent",
                    "node": {"template": {"code": {"value": code}}, "metadata": {"code_hash": code_hash}},
                },
            }
        ],
        "edges": [],
    }


@pytest.mark.parametrize("import_line", [_MODELS_IMPORT, _HELPERS_IMPORT])
def test_rewrite_agent_code_scopes_recognized_imports(migration, import_line):
    new_code = migration._rewrite_agent_code(_stale_agent_code(import_line=import_line))
    assert new_code is not None
    # Vulnerable call is gone; scoped call + helper are present and imported.
    assert "MemoryComponent(**self.get_base_args())" not in new_code
    assert "aget_agent_chat_history(" in new_code
    assert "user_id=_safe_graph_user_id(self)" in new_code
    assert f"{import_line}, _safe_graph_user_id, aget_agent_chat_history" in new_code
    # MemoryComponent() (no-arg, for memory_inputs) is preserved.
    assert "MemoryComponent().inputs" in new_code


def test_rewrite_agent_code_skips_unrecognized_import(migration):
    code = _stale_agent_code(import_line="from lfx.components.somewhere.memory import MemoryComponent")
    # Old method present, but import path is unknown: must skip rather than emit a module
    # that references undefined helper names.
    assert migration._rewrite_agent_code(code) is None


def test_rewrite_agent_code_skips_already_fixed(migration):
    assert migration._rewrite_agent_code("class AgentComponent:\n    pass\n") is None
    assert migration._rewrite_agent_code(None) is None


def _make_flow_table():
    engine = sa.create_engine("sqlite://")
    meta = sa.MetaData()
    flow = sa.Table(
        "flow",
        meta,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("data", sa.JSON),
    )
    meta.create_all(engine)
    return engine, flow


def _load(engine, flow, id_):
    with engine.begin() as conn:
        row = conn.execute(sa.select(flow.c.data).where(flow.c.id == id_)).first()
    return row[0]


def _run_upgrade(migration, engine):
    with engine.begin() as conn:
        migration.op = types.SimpleNamespace(get_bind=lambda: conn)
        migration.upgrade()


def test_upgrade_rewrites_seeded_rows_and_is_idempotent(migration):
    engine, flow = _make_flow_table()
    stale = _agent_flow_data(_stale_agent_code(import_line=_MODELS_IMPORT), code_hash="deadbeef0000")
    helpers_stale = _agent_flow_data(_stale_agent_code(import_line=_HELPERS_IMPORT), code_hash="deadbeef1111")
    unrecognized = _agent_flow_data(
        _stale_agent_code(import_line="from lfx.components.somewhere.memory import MemoryComponent"),
        code_hash="deadbeef2222",
    )
    non_agent = {
        "nodes": [{"id": "ChatInput-1", "data": {"type": "ChatInput", "node": {"template": {}, "metadata": {}}}}],
        "edges": [],
    }

    with engine.begin() as conn:
        conn.execute(
            flow.insert(),
            [
                {"id": "stale", "data": stale},
                {"id": "helpers", "data": helpers_stale},
                {"id": "unrec", "data": unrecognized},
                {"id": "plain", "data": non_agent},
            ],
        )

    _run_upgrade(migration, engine)

    for id_ in ("stale", "helpers"):
        node = _load(engine, flow, id_)["nodes"][0]["data"]["node"]
        code = node["template"]["code"]["value"]
        assert "MemoryComponent(**self.get_base_args())" not in code
        assert "user_id=_safe_graph_user_id(self)" in code
        # code_hash restamped and self-consistent with the rewritten code.
        assert node["metadata"]["code_hash"] == hashlib.sha256(code.encode()).hexdigest()[:12]
        assert node["metadata"]["code_hash"] not in ("deadbeef0000", "deadbeef1111")

    # Unrecognized-import row left byte-for-byte intact (still vulnerable, but never broken).
    unrec_node = _load(engine, flow, "unrec")["nodes"][0]["data"]["node"]
    original_unrec_code = unrecognized["nodes"][0]["data"]["node"]["template"]["code"]["value"]
    assert unrec_node["template"]["code"]["value"] == original_unrec_code
    assert unrec_node["metadata"]["code_hash"] == "deadbeef2222"

    # Non-Agent flow untouched.
    assert _load(engine, flow, "plain") == non_agent

    # Idempotent: a second run changes nothing.
    before = {id_: _load(engine, flow, id_) for id_ in ("stale", "helpers", "unrec", "plain")}
    _run_upgrade(migration, engine)
    after = {id_: _load(engine, flow, id_) for id_ in ("stale", "helpers", "unrec", "plain")}
    assert before == after


def test_upgrade_converges_packaged_flow_to_committed_fix(migration):
    """A row seeded with the pre-fix LangflowAssistant snapshot converges to the shipped fix."""
    import json

    flows_dir = Path(langflow.__file__).parent / "agentic" / "flows"
    fixed = json.loads((flows_dir / "LangflowAssistant.json").read_text())
    fixed_data = fixed["data"]

    # Reconstruct the pre-fix row by reversing the shipped rewrite on every Agent node.
    stale_data = json.loads(json.dumps(fixed_data))
    reversed_any = False
    for node in stale_data["nodes"]:
        nd = node.get("data", {})
        if nd.get("type") != "Agent":
            continue
        code = nd["node"]["template"]["code"]["value"]
        old_code = code.replace(migration._NEW_METHOD, migration._OLD_METHOD, 1)
        for old_imp, new_imp in migration._OLD_TO_NEW_IMPORT.items():
            old_code = old_code.replace(new_imp, old_imp, 1)
        nd["node"]["template"]["code"]["value"] = old_code
        nd["node"]["metadata"]["code_hash"] = hashlib.sha256(old_code.encode()).hexdigest()[:12]
        reversed_any = True
    assert reversed_any, "LangflowAssistant.json has no Agent node — test needs updating"

    engine, flow = _make_flow_table()
    with engine.begin() as conn:
        conn.execute(flow.insert(), [{"id": "seeded", "data": stale_data}])

    _run_upgrade(migration, engine)

    result = _load(engine, flow, "seeded")

    def agent_snaps(data):
        return {
            n["id"]: (n["data"]["node"]["template"]["code"]["value"], n["data"]["node"]["metadata"]["code_hash"])
            for n in data["nodes"]
            if n.get("data", {}).get("type") == "Agent"
        }

    assert agent_snaps(result) == agent_snaps(fixed_data)
