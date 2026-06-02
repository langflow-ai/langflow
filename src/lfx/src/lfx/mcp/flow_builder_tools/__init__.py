"""Tools for searching components and building flows on the user's canvas.

These components expose flow_builder capabilities as Agent tools.
Each mutating tool pushes a flow_update event to a per-request queue
so the assistant service can send real-time SSE updates to the frontend.

This module is a thin re-export surface: the implementation lives in
responsibility-scoped submodules.

  - ``_state``      — per-request working-flow + emit + drain + lifecycle
                       (plus the tiny ``_find_node`` / ``_readable_preview``
                       node-shape utilities every tool layer needs)
  - ``read_tools``  — Search / Describe / GetFieldValue / DescribeFlowIO
                       (pure reads, no events)
  - ``edit_tools``  — ProposeFieldEdit (validated, user-reviewable)
  - ``mutate_tools``— Add / Remove / Connect / Configure (push events)
  - ``run_tools``   — Propose / Build / Run / Generate
                       (orchestration + run helpers)

Importing from ``lfx.mcp.flow_builder_tools`` keeps the original public
surface — every prior caller's ``from lfx.mcp.flow_builder_tools import X``
continues to resolve unchanged.
"""

from __future__ import annotations

# Per-request state + small shared utilities. Re-exported so the public
# surface of ``lfx.mcp.flow_builder_tools`` is unchanged.
from ._state import _emit as _emit
from ._state import _ensure_working_flow as _ensure_working_flow
from ._state import _find_node as _find_node
from ._state import _load_registry_user_aware as _load_registry_user_aware
from ._state import _readable_preview as _readable_preview
from ._state import (
    drain_flow_events,
    get_working_flow,
    init_working_flow,
    isolate_flow_run_context,
    node_existed_at_start,
    reset_working_flow,
    set_propose_existing_edits,
    should_propose_existing_edits,
)
from .edit_tools import ProposeFieldEdit
from .mutate_tools import (
    AddComponent,
    ConfigureComponent,
    ConnectComponents,
    RemoveComponent,
)
from .read_tools import (
    DescribeComponentType,
    DescribeFlowIO,
    GetFieldValue,
    SearchComponentTypes,
)
from .run_tools import (
    BuildFlowFromSpec,
    GenerateComponent,
    ProposePlan,
    RunFlow,
)

__all__ = [
    "AddComponent",
    "BuildFlowFromSpec",
    "ConfigureComponent",
    "ConnectComponents",
    "DescribeComponentType",
    "DescribeFlowIO",
    "GenerateComponent",
    "GetFieldValue",
    "ProposeFieldEdit",
    "ProposePlan",
    "RemoveComponent",
    "RunFlow",
    "SearchComponentTypes",
    "drain_flow_events",
    "get_working_flow",
    "init_working_flow",
    "isolate_flow_run_context",
    "node_existed_at_start",
    "reset_working_flow",
    "set_propose_existing_edits",
    "should_propose_existing_edits",
]
