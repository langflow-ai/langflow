// `actorNode` — a human participant (User, Admin, …) in a sequence diagram.
// A person glyph above the label in a rounded card, styled with the lothal
// theme tokens so it inherits light/dark from the surrounding surface. A target
// handle on the left and a source handle on the right let messages route
// between participants laid out left-to-right.

import { Handle, type Node, type NodeProps, Position } from "@xyflow/react";
import { memo } from "react";
import { type CanvasNodeData, HANDLE_STYLE } from "./nodeStyles";

type ActorFlowNode = Node<CanvasNodeData, "actorNode">;

function PersonGlyph() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="8" r="3.4" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M5.5 19c0-3.3 2.9-5.5 6.5-5.5s6.5 2.2 6.5 5.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ActorNodeImpl({ data }: NodeProps<ActorFlowNode>) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
        minWidth: 84,
        padding: "10px 14px",
        background: "var(--surface)",
        border: "1px solid var(--border-strong)",
        borderRadius: 12,
        color: "var(--ink)",
        boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
      }}
    >
      <Handle type="target" position={Position.Left} style={HANDLE_STYLE} />
      <span style={{ color: "var(--accent)" }}>
        <PersonGlyph />
      </span>
      <span style={{ fontSize: 12.5, fontWeight: 500, textAlign: "center" }}>
        {data.label ?? "Actor"}
      </span>
      {data.note && (
        <span style={{ fontSize: 10, color: "var(--ink-soft)" }}>
          {data.note}
        </span>
      )}
      {data.kind && (
        <span
          aria-label={`kind: ${data.kind}`}
          style={{
            fontSize: 9,
            fontWeight: 500,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--ink-faint)",
            marginTop: 2,
          }}
        >
          {data.kind}
        </span>
      )}
      <Handle type="source" position={Position.Right} style={HANDLE_STYLE} />
    </div>
  );
}

export const ActorNode = memo(ActorNodeImpl);
