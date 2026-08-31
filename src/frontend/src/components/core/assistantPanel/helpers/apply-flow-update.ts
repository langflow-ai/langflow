/**
 * Maps a single SSE `flow_update` event onto the live canvas. Reads/writes
 * `useFlowStore.getState()` directly (bypassing React subscription) so a rapid
 * event drain grabs the freshest state per call. `updateNodeInternals` is
 * passed in because it is a hook return value.
 */

import type { useUpdateNodeInternals } from "@xyflow/react";
import type { AgenticFlowUpdateEvent } from "@/controllers/API/queries/agentic";
import useFlowStore from "@/stores/flowStore";

type UpdateNodeInternals = ReturnType<typeof useUpdateNodeInternals>;

// SSE flow_update payloads are LLM-driven (untrusted); validate before any
// store mutation so a malformed event can't silently corrupt the canvas.
const isPlainObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isNonEmptyString = (v: unknown): v is string =>
  typeof v === "string" && v.length > 0;
const isNodeShape = (v: unknown): v is Record<string, unknown> =>
  isPlainObject(v) && isNonEmptyString((v as Record<string, unknown>).id);

const warnDrop = (action: string, reason: string): void => {
  console.warn(`[applyFlowUpdate] dropped ${action}: ${reason}`);
};

/**
 * Notify each new node once mounted so their handles register. Kept minimal —
 * the loop-edge redraw is handled by applying nodes+edges atomically (see the
 * `set_flow` case); this just nudges React Flow for dynamic handles.
 */
export function notifyNodesUntilMounted(
  nodeIds: string[],
  updateNodeInternals: UpdateNodeInternals,
  onFinalPass?: () => void,
): void {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      for (const id of nodeIds) updateNodeInternals(id);
      onFinalPass?.();
    });
  });
}

export function applyFlowUpdate(
  event: AgenticFlowUpdateEvent,
  updateNodeInternals: UpdateNodeInternals,
): void {
  switch (event.action) {
    case "set_flow": {
      const flow = event.flow as {
        data?: { nodes?: unknown[]; edges?: unknown[] };
      };
      const nodes = flow?.data?.nodes;
      const edges = flow?.data?.edges;
      if (!Array.isArray(nodes)) {
        warnDrop("set_flow", "flow.data.nodes is not an array");
        break;
      }
      if (edges !== undefined && !Array.isArray(edges)) {
        warnDrop("set_flow", "flow.data.edges is not an array");
        break;
      }
      {
        // Atomic nodes+edges in one render so React Flow resolves edges to
        // loop/dynamic handles immediately (a split set draws them only on refresh).
        useFlowStore
          .getState()
          .setNodesAndEdges(nodes as never[], (edges ?? []) as never[]);
        const newNodeIds = nodes
          .map((n) => (isPlainObject(n) ? n.id : undefined))
          .filter(isNonEmptyString);
        notifyNodesUntilMounted(newNodeIds, updateNodeInternals, () =>
          useFlowStore.getState().reactFlowInstance?.fitView({
            padding: { left: "20px", right: "20px", top: "80px" },
            minZoom: 0.25,
            maxZoom: 2,
            duration: 250,
          }),
        );
      }
      break;
    }
    case "add_component": {
      const node = event.node;
      if (!isNodeShape(node)) {
        warnDrop("add_component", "node is not an object with a string id");
        break;
      }
      const setNodes = useFlowStore.getState().setNodes;
      setNodes((prev) => [...prev, node as never]);
      break;
    }
    case "connect": {
      const edge = event.edge;
      if (!isPlainObject(edge)) {
        warnDrop("connect", "edge is not an object");
        break;
      }
      const src = edge.source;
      const tgt = edge.target;
      if (!isNonEmptyString(src) || !isNonEmptyString(tgt)) {
        warnDrop("connect", "edge.source/target missing or not strings");
        break;
      }
      const setEdges = useFlowStore.getState().setEdges;
      setEdges((prev) => [...prev, edge as never]);
      // Refresh both endpoints so ReactFlow reconciles handle positions.
      updateNodeInternals(src);
      updateNodeInternals(tgt);
      break;
    }
    case "remove_component": {
      const nodeId = event.component_id as string;
      if (nodeId) {
        const setNodes = useFlowStore.getState().setNodes;
        const setEdges = useFlowStore.getState().setEdges;
        setNodes((prev) =>
          prev.filter((n) => (n as Record<string, unknown>).id !== nodeId),
        );
        setEdges((prev) =>
          prev.filter((e) => {
            const edge = e as Record<string, unknown>;
            return edge.source !== nodeId && edge.target !== nodeId;
          }),
        );
      }
      break;
    }
    case "configure": {
      const compId = event.component_id as string;
      const params = event.params as Record<string, unknown>;
      if (compId && params) {
        const setNodes = useFlowStore.getState().setNodes;
        setNodes((prev) =>
          prev.map((n) => {
            const node = n as Record<string, unknown>;
            if (node.id !== compId) return n;
            const data = node.data as Record<string, unknown>;
            const innerNode = (data?.node ?? {}) as Record<string, unknown>;
            const tpl = (innerNode?.template ?? {}) as Record<string, unknown>;
            return {
              ...node,
              data: {
                ...data,
                node: {
                  ...innerNode,
                  template: {
                    ...tpl,
                    ...Object.fromEntries(
                      Object.entries(params).map(([k, v]) => [
                        k,
                        {
                          ...(tpl[k] as Record<string, unknown>),
                          value: v,
                        },
                      ]),
                    ),
                  },
                },
              },
            } as never;
          }),
        );
      }
      break;
    }
    case "select_output": {
      // `data.selected_output` (top-level, not inside data.node) switches which
      // output handle renders; notify so the moved handle is reconciled.
      const compId = event.component_id as string;
      const outputName = event.output_name as string;
      if (compId && outputName) {
        const setNodes = useFlowStore.getState().setNodes;
        setNodes((prev) =>
          prev.map((n) => {
            const node = n as Record<string, unknown>;
            if (node.id !== compId) return n;
            const data = (node.data ?? {}) as Record<string, unknown>;
            return {
              ...node,
              data: {
                ...data,
                selected_output: outputName,
              },
            } as never;
          }),
        );
        updateNodeInternals(compId);
      }
      break;
    }
    case "set_connection_mode": {
      // `data._connectionMode` flips ModelInput to a left handle for an external
      // model edge; notify so the new handle position is reconciled.
      const compId = event.component_id as string;
      const enabled = event.enabled as boolean;
      if (compId !== undefined) {
        const setNodes = useFlowStore.getState().setNodes;
        setNodes((prev) =>
          prev.map((n) => {
            const node = n as Record<string, unknown>;
            if (node.id !== compId) return n;
            const data = (node.data ?? {}) as Record<string, unknown>;
            return {
              ...node,
              data: {
                ...data,
                _connectionMode: enabled,
              },
            } as never;
          }),
        );
        updateNodeInternals(compId);
      }
      break;
    }
    case "enable_tool_mode": {
      // Mirror the backend Tool Mode flip (outputs collapse to one Toolset
      // handle) BEFORE the connect edge, else its source handle has no match.
      const compId = event.component_id as string;
      const outputs = event.outputs;
      if (compId && Array.isArray(outputs)) {
        const setNodes = useFlowStore.getState().setNodes;
        setNodes((prev) =>
          prev.map((n) => {
            const node = n as Record<string, unknown>;
            if (node.id !== compId) return n;
            const data = (node.data ?? {}) as Record<string, unknown>;
            const innerNode = (data?.node ?? {}) as Record<string, unknown>;
            return {
              ...node,
              data: {
                ...data,
                node: {
                  ...innerNode,
                  tool_mode: true,
                  outputs,
                },
              },
            } as never;
          }),
        );
        updateNodeInternals(compId);
      }
      break;
    }
    default:
      break;
  }
}
