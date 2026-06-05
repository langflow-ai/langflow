// Top bar with three slots: left (brand / back), center (phase indicator),
// right (actions). `dense` tightens it for the workspace.

import type { ReactNode } from "react";

export function TopBar({
  left,
  center,
  right,
  dense,
}: {
  left?: ReactNode;
  center?: ReactNode;
  right?: ReactNode;
  dense?: boolean;
}) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: dense ? "10px 18px" : "14px 22px",
        borderBottom: "1px solid var(--border)",
        background: "var(--paper)",
        gap: 16,
        minHeight: dense ? 48 : 56,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          minWidth: 0,
        }}
      >
        {left}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {center}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          minWidth: 0,
          justifyContent: "flex-end",
        }}
      >
        {right}
      </div>
    </header>
  );
}
