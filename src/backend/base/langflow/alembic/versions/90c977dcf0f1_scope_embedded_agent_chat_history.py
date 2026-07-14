# ruff: noqa: E501
"""Scope embedded Agent chat-history reads to the executing user.

Revision ID: 90c977dcf0f1
Revises: 826cfcc8c8a0
Create Date: 2026-07-14 00:00:01.000000

Phase: MIGRATE
"""

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "90c977dcf0f1"  # pragma: allowlist secret
down_revision: str | None = "826cfcc8c8a0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_MARKER = "MemoryComponent(**self.get_base_args())"
_FLOW_SCOPED_MARKER = "aget_agent_chat_history("

_LEGACY_METHOD = (
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

_FLOW_SCOPED_METHOD = (
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
    '            message for message in messages if getattr(message, "id", None) != getattr(self.input_value, "id", None)\n'
    "        ]\n"
)

_USER_SCOPED_METHOD = _FLOW_SCOPED_METHOD.replace(
    "            n_messages=self.n_messages,\n",
    "            n_messages=self.n_messages,\n            user_id=_safe_graph_user_id(self),\n",
)

_IMPORT_REWRITES = {
    "from lfx.components.models_and_agents.memory import MemoryComponent\n": (
        "from lfx.components.models_and_agents.memory import "
        "MemoryComponent, _safe_graph_user_id, aget_agent_chat_history\n"
    ),
    "from lfx.components.helpers.memory import MemoryComponent\n": (
        "from lfx.components.helpers.memory import MemoryComponent, _safe_graph_user_id, aget_agent_chat_history\n"
    ),
    "from lfx.components.models_and_agents.memory import MemoryComponent, aget_agent_chat_history\n": (
        "from lfx.components.models_and_agents.memory import "
        "MemoryComponent, _safe_graph_user_id, aget_agent_chat_history\n"
    ),
}


def _rewrite_agent_code(code: object) -> str | None:
    """Return the owner-scoped rewrite of a known Agent snapshot."""
    if not isinstance(code, str) or "user_id=_safe_graph_user_id(self)" in code:
        return None
    old_method = _LEGACY_METHOD if _LEGACY_METHOD in code else _FLOW_SCOPED_METHOD
    if old_method not in code:
        return None
    for old_import, new_import in _IMPORT_REWRITES.items():
        if old_import in code:
            return code.replace(old_import, new_import, 1).replace(old_method, _USER_SCOPED_METHOD, 1)
    return None


def _rewrite_flow_data(data: object) -> bool:
    """Patch stale Agent nodes in a flow, including nested group flows."""
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
        if not isinstance(node_data, dict):
            continue
        inner = node_data.get("node")
        if not isinstance(inner, dict):
            continue
        if node_data.get("type") == "Agent":
            template = inner.get("template")
            code_field = template.get("code") if isinstance(template, dict) else None
            if isinstance(code_field, dict):
                new_code = _rewrite_agent_code(code_field.get("value"))
                if new_code is not None:
                    code_field["value"] = new_code
                    metadata = inner.get("metadata")
                    if isinstance(metadata, dict):
                        metadata["code_hash"] = hashlib.sha256(new_code.encode()).hexdigest()[:12]
                    changed = True
        nested_flow = inner.get("flow")
        nested_data = nested_flow.get("data") if isinstance(nested_flow, dict) else None
        if _rewrite_flow_data(nested_data):
            changed = True
    return changed


def upgrade() -> None:
    conn = op.get_bind()
    meta = sa.MetaData()
    flow = sa.Table("flow", meta, sa.Column("id"), sa.Column("data", sa.JSON))
    serialized = sa.cast(flow.c.data, sa.Text)
    stmt = sa.select(flow.c.id, flow.c.data).where(
        sa.or_(serialized.like(f"%{_LEGACY_MARKER}%"), serialized.like(f"%{_FLOW_SCOPED_MARKER}%"))
    )
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
    # Reverting would reintroduce cross-user disclosure, and original snapshots
    # cannot be reconstructed safely.
    return
