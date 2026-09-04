# ruff: noqa: E501
"""scope embedded agent chat-history in legacy flows

Phase: MIGRATE

Historic Langflow releases seeded the agentic assistant flows (LangflowAssistant,
SystemMessageGen, TemplateAssistant) into each user's "Langflow Assistant" folder on
login, and users could also build their own flows with the Agent component. Every such
Flow row embeds a snapshot of the Agent component source in
``node.data.node.template.code.value``. In the pre-fix snapshot ``get_memory_data`` read
chat history via ``MemoryComponent(**self.get_base_args()).retrieve_messages()`` — an
unscoped read that can disclose another user's messages on a shared ``session_id``
(CWE-200), because ``get_base_args()`` passes no graph so the user-scoping helper falls
back to ``None``.

The packaged JSON snapshots and the component index were fixed in code, but the
login-time seeding path was removed in #11058, so already-seeded rows are never
refreshed. This one-time data migration rewrites the embedded ``get_memory_data`` in
existing Flow rows to the scoped
``aget_agent_chat_history(..., user_id=_safe_graph_user_id(self))`` path — where ``self``
is the Agent and therefore carries ``self.graph`` (the executing user) — and restamps
the node's ``code_hash``.

The rewrite is:
  * surgical  — only the MemoryComponent import line and the ``get_memory_data`` method
    body are replaced;
  * idempotent — rows are matched by the pre-fix pattern, which the rewrite removes, so a
    second run is a no-op;
  * safe      — a node is skipped unless BOTH the exact old method body and a recognized
    MemoryComponent import are present, so an unrecognized snapshot is left intact rather
    than being turned into a ``NameError`` for the new helper names.

Revision ID: b2c72e1e1439
Revises: 9b3e7c1f0a52
Create Date: 2026-06-30 17:20:35.841736

"""

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c72e1e1439"  # pragma: allowlist secret
down_revision: str | None = "9b3e7c1f0a52"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Distinctive fragment present only in the pre-fix ``get_memory_data`` (the fixed snapshot
# calls ``aget_agent_chat_history`` instead, and only references ``MemoryComponent()`` with
# no args). Used to prefilter rows at the SQL layer so only flows that could carry the old
# snapshot are loaded. The Python matcher below is the precise gate; this is just a cheap
# over-inclusive narrowing (SQL ``LIKE`` treats ``_`` as a wildcard, which only widens it).
_PREFILTER_MARKER = "MemoryComponent(**self.get_base_args())"

_OLD_METHOD = (
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
    '            message for message in messages if getattr(message, "id", None) != getattr(self.input_value, "id", None)\n'
    "        ]\n"
)

_NEW_METHOD = (
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
    "            user_id=_safe_graph_user_id(self),\n"
    "        )\n"
    "        return [\n"
    '            message for message in messages if getattr(message, "id", None) != getattr(self.input_value, "id", None)\n'
    "        ]\n"
)

# Recognized MemoryComponent import lines -> the same import extended with the two scoped
# helpers. A node whose import matches none of these is skipped (see module docstring).
_OLD_TO_NEW_IMPORT = {
    "from lfx.components.models_and_agents.memory import MemoryComponent\n": (
        "from lfx.components.models_and_agents.memory import MemoryComponent, _safe_graph_user_id, aget_agent_chat_history\n"
    ),
    "from lfx.components.helpers.memory import MemoryComponent\n": (
        "from lfx.components.helpers.memory import MemoryComponent, _safe_graph_user_id, aget_agent_chat_history\n"
    ),
}


def _rewrite_agent_code(code: object) -> str | None:
    """Return the scoped rewrite of an embedded Agent snapshot, or ``None`` to skip it."""
    if not isinstance(code, str) or _OLD_METHOD not in code:
        return None
    for old_import, new_import in _OLD_TO_NEW_IMPORT.items():
        if old_import in code:
            return code.replace(old_import, new_import, 1).replace(_OLD_METHOD, _NEW_METHOD, 1)
    # Old method present but import path unrecognized: skip rather than emit a module that
    # references undefined names (aget_agent_chat_history / _safe_graph_user_id).
    return None


def _rewrite_flow_data(data: object) -> bool:
    """Patch every stale Agent node in ``data`` in place. Returns True if anything changed."""
    if not isinstance(data, dict):
        return False
    nodes = data.get("nodes")
    if not isinstance(nodes, list):
        return False
    changed = False
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data")
        if not isinstance(node_data, dict) or node_data.get("type") != "Agent":
            continue
        inner = node_data.get("node")
        if not isinstance(inner, dict):
            continue
        template = inner.get("template")
        code_field = template.get("code") if isinstance(template, dict) else None
        if not isinstance(code_field, dict):
            continue
        new_code = _rewrite_agent_code(code_field.get("value"))
        if new_code is None:
            continue
        code_field["value"] = new_code
        metadata = inner.get("metadata")
        if isinstance(metadata, dict):
            metadata["code_hash"] = hashlib.sha256(new_code.encode()).hexdigest()[:12]
        changed = True
    return changed


def upgrade() -> None:
    conn = op.get_bind()
    # Minimal table with only the columns we touch. ``data`` is typed ``JSON`` so its
    # bind/result processors handle (de)serialization on both SQLite and PostgreSQL;
    # ``id`` is left untyped so we round-trip the raw primary-key value and avoid the
    # ``Uuid`` bind processor (a str vs UUID mismatch there caused the LE-1675 crash).
    meta = sa.MetaData()
    flow = sa.Table("flow", meta, sa.Column("id"), sa.Column("data", sa.JSON))
    # Prefilter at the DB so we only pull flows that could carry the pre-fix snapshot.
    stmt = sa.select(flow.c.id, flow.c.data).where(sa.cast(flow.c.data, sa.Text).like(f"%{_PREFILTER_MARKER}%"))
    for row in conn.execute(stmt).fetchall():
        data = row.data
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (TypeError, ValueError):
                continue
        if _rewrite_flow_data(data):
            conn.execute(sa.update(flow).where(flow.c.id == row.id).values(data=data))


def downgrade() -> None:
    # No-op: this migration only rewrites unscoped chat-history reads to their scoped
    # equivalent. Reverting would re-introduce a cross-user disclosure (CWE-200), and the
    # original per-row snapshot is not reconstructable, so there is nothing safe to undo.
    pass
