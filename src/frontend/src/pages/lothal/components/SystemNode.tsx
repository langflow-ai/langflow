// `systemNode` — a system, service, or interface (Chat Interface, LLM Engine,
// …). A plain rounded rectangle with a centred label, styled with the lothal
// theme tokens. Like the actor node it carries a left target / right source
// handle so messages route between horizontally-laid-out participants.

import { Handle, type Node, type NodeProps, Position } from "@xyflow/react";
import { memo } from "react";
import { type CanvasNodeData, HANDLE_STYLE } from "./nodeStyles";

type SystemFlowNode = Node<CanvasNodeData, "systemNode">;

function SystemNodeImpl({ data }: NodeProps<SystemFlowNode>) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 2,
        minWidth: 120,
        padding: "12px 18px",
        background: "var(--surface-2)",
        border: "1px solid var(--border-strong)",
        borderRadius: 10,
        color: "var(--ink)",
        boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
      }}
    >
      <Handle type="target" position={Position.Left} style={HANDLE_STYLE} />
      <span style={{ fontSize: 12.5, fontWeight: 500, textAlign: "center" }}>
        {data.label ?? "System"}
      </span>
      {data.note && (
        <span style={{ fontSize: 10, color: "var(--ink-soft)" }}>
          {data.note}
        </span>
      )}
      <Handle type="source" position={Position.Right} style={HANDLE_STYLE} />
    </div>
  );
}

export const SystemNode = memo(SystemNodeImpl);
