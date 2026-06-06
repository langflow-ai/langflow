// Canvas legend — explains the three edge kinds (sync / return / async) the way
// they're drawn on the canvas. Floats in a corner of <DiagramCanvas>; its line
// samples mirror exactly what `edgeStyle` produces for each kind.

import type { EdgeKind } from "@/controllers/API/queries/lothal";
import { edgeStyle } from "./canvasGraph";

const ENTRIES: { kind: EdgeKind; label: string }[] = [
  { kind: "sync", label: "Call" },
  { kind: "return", label: "Return" },
  { kind: "async", label: "Async" },
];

function LineSample({ kind }: { kind: EdgeKind }) {
  const { stroke, strokeDasharray } = edgeStyle(kind);
  return (
    <svg width="26" height="8" viewBox="0 0 26 8" aria-hidden>
      <line
        x1="1"
        y1="4"
        x2="19"
        y2="4"
        stroke={stroke}
        strokeWidth="1.6"
        strokeDasharray={strokeDasharray}
      />
      <path
        d="M19 4 L15 1.5 M19 4 L15 6.5"
        stroke={stroke}
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}

export function CanvasLegend() {
  return (
    <div
      role="group"
      aria-label="Edge legend"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        padding: "10px 12px",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
      }}
    >
      <span className="label" style={{ fontSize: 9 }}>
        Messages
      </span>
      {ENTRIES.map((e) => (
        <div
          key={e.kind}
          style={{ display: "flex", alignItems: "center", gap: 8 }}
        >
          <LineSample kind={e.kind} />
          <span style={{ fontSize: 11, color: "var(--ink-mute)" }}>
            {e.label}
          </span>
        </div>
      ))}
    </div>
  );
}
