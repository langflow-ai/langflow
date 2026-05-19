/**
 * Reducer-style applier that maps a single SSE ``flow_update`` event onto
 * the live canvas state. Extracted from `use-assistant-chat.ts` so the hook
 * stays focused on streaming + message state, and so each switch case can
 * be diffed independently when the event protocol evolves.
 *
 * Coupling notes:
 *   - Reads/writes via `useFlowStore.getState()` directly. This bypasses
 *     React's reactive subscription on purpose: applying many events in
 *     quick succession (e.g. during a build_flow drain) is faster when each
 *     case grabs the freshest state at call time.
 *   - Takes `updateNodeInternals` as an argument because it is a React hook
 *     return value and cannot be called outside a component.
 */

import type { useUpdateNodeInternals } from "@xyflow/react";
import type { AgenticFlowUpdateEvent } from "@/controllers/API/queries/agentic";
import useFlowStore from "@/stores/flowStore";

type UpdateNodeInternals = ReturnType<typeof useUpdateNodeInternals>;

export function applyFlowUpdate(
  event: AgenticFlowUpdateEvent,
  updateNodeInternals: UpdateNodeInternals,
): void {
  switch (event.action) {
    case "set_flow": {
      const flow = event.flow as {
        data?: { nodes?: unknown[]; edges?: unknown[] };
      };
      if (flow?.data?.nodes) {
        const setNodes = useFlowStore.getState().setNodes;
        const setEdges = useFlowStore.getState().setEdges;
        setNodes(flow.data.nodes as never[]);
        setEdges((flow.data.edges ?? []) as never[]);
        // A whole-canvas replace lands the new flow wherever the old
        // viewport happened to be (often off-screen). Frame it like the
        // app's own flow-load path (PageComponent): a SINGLE deferred
        // frame fires before React Flow has measured the new nodes, which
        // produces the wrong/"weird" zoom — wait two frames so layout has
        // settled, and bound the zoom so a tiny flow isn't over-zoomed.
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            useFlowStore.getState().reactFlowInstance?.fitView({
              padding: { left: "20px", right: "20px", top: "80px" },
              minZoom: 0.25,
              maxZoom: 2,
              duration: 250,
            });
          });
        });
      }
      break;
    }
    case "add_component": {
      const node = event.node as Record<string, unknown>;
      if (node) {
        const setNodes = useFlowStore.getState().setNodes;
        setNodes((prev) => [...prev, node as never]);
      }
      break;
    }
    case "connect": {
      const edge = event.edge as Record<string, unknown>;
      if (edge) {
        const setEdges = useFlowStore.getState().setEdges;
        setEdges((prev) => [...prev, edge as never]);
        // Refresh both endpoints so ReactFlow reconciles handle positions
        // and renders the new edge between them.
        const src = edge.source as string | undefined;
        const tgt = edge.target as string | undefined;
        if (src) updateNodeInternals(src);
        if (tgt) updateNodeInternals(tgt);
      }
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
      // The frontend's GenericNode reads `data.selected_output` (top-level
      // on the ReactFlow node data, NOT inside data.node) to decide which
      // output's handle to render and which label to show in the
      // dropdown. Patch at the same level so OpenAIModel switches from
      // "Model Response" to "Language Model" when wired via model_output.
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
        // The selected output's handle is the only one rendered for nodes
        // with multiple outputs, so the handle position changes when we
        // switch which output is "active" — refresh ReactFlow's cache.
        updateNodeInternals(compId);
      }
      break;
    }
    case "set_connection_mode": {
      // ModelInput dropdown reads `data._connectionMode` to switch from
      // its inline model picker to "Connect other models" mode (which
      // exposes the left handle for an external model edge). Mirror the
      // backend flip so the connected edge actually renders.
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
        // Toggling _connectionMode swaps the model field's UI between an
        // inline dropdown and a connection handle. The handle's DOM
        // position changes — without this notification ReactFlow keeps
        // the cached position and the edge can't find its target.
        updateNodeInternals(compId);
      }
      break;
    }
    default:
      break;
  }
}
