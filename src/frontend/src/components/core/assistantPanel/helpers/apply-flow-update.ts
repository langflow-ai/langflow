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

// I6: SSE flow_update events come from the assistant stream (LLM-driven) and
// are untrusted. Cast-and-write lets a malformed payload corrupt the canvas
// with no signal — these predicates reject the event before any store mutation.
const isPlainObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isNonEmptyString = (v: unknown): v is string =>
  typeof v === "string" && v.length > 0;
const isNodeShape = (v: unknown): v is Record<string, unknown> =>
  isPlainObject(v) && isNonEmptyString((v as Record<string, unknown>).id);

const warnDrop = (action: string, reason: string): void => {
  // Visible at the dev console; lets protocol drift surface instead of
  // silently corrupting the canvas.
  console.warn(`[applyFlowUpdate] dropped ${action}: ${reason}`);
};

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
        const setNodes = useFlowStore.getState().setNodes;
        const setEdges = useFlowStore.getState().setEdges;
        setNodes(nodes as never[]);
        setEdges((edges ?? []) as never[]);
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
      // Refresh both endpoints so ReactFlow reconciles handle positions
      // and renders the new edge between them.
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
    case "enable_tool_mode": {
      // The backend flipped the source component into Tool Mode when wiring
      // `X.component_as_tool -> Agent.tools` (its outputs collapsed to the
      // single synthesized `component_as_tool`/Toolset output). Mirror that on
      // the canvas BEFORE the `connect` edge is applied — otherwise the node
      // still renders its old output handle, the edge's `component_as_tool`
      // source handle has no match, and the edge silently never renders.
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
        // The node's output handles changed (collapsed to one Toolset handle),
        // so ReactFlow must recompute handle positions or the edge to
        // component_as_tool can't find its source.
        updateNodeInternals(compId);
      }
      break;
    }
    default:
      break;
  }
}
