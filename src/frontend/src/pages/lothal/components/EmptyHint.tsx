// Centered empty state: a serif italic title, optional sub-line, and an
// optional keyboard hint chip.

import type { ReactNode } from "react";

export function EmptyHint({
  title,
  sub,
  kbd,
}: {
  title: ReactNode;
  sub?: ReactNode;
  kbd?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
        padding: 40,
        textAlign: "center",
      }}
    >
      <div
        className="serif"
        style={{ fontSize: 26, color: "var(--ink-mute)", fontStyle: "italic" }}
      >
        {title}
      </div>
      {sub && (
        <div style={{ fontSize: 13, color: "var(--ink-soft)", maxWidth: 360 }}>
          {sub}
        </div>
      )}
      {kbd && (
        <div
          className="mono"
          style={{
            fontSize: 11,
            padding: "3px 8px",
            borderRadius: 5,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            color: "var(--ink-soft)",
            marginTop: 6,
          }}
        >
          {kbd}
        </div>
      )}
    </div>
  );
}
