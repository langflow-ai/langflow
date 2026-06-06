// `systemNode` — a system, service, or interface (Chat Interface, LLM Engine,
// …). A plain rounded rectangle with a centred label, styled with the lothal
// theme tokens. Like the actor node it carries a left target / right source
// handle so messages route between horizontally-laid-out participants.

import { Handle, type NodeProps, Position } from "@xyflow/react";
import { memo } from "react";

const handleStyle = {
  width: 7,
  height: 7,
  background: "var(--accent)",
  border: "none",
} as const;

function SystemNodeImpl({ data }: NodeProps) {
  const d = data as { label?: string; note?: string };
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
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <span style={{ fontSize: 12.5, fontWeight: 500, textAlign: "center" }}>
        {d.label ?? "System"}
      </span>
      {d.note && (
        <span style={{ fontSize: 10, color: "var(--ink-soft)" }}>{d.note}</span>
      )}
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </div>
  );
}

export const SystemNode = memo(SystemNodeImpl);
