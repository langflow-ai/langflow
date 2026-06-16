// A centered system note in the chat stream — used to mark a phase transition
// ("Requirements clear · moving to Sketch"). Distinct from a message bubble: it
// reads as Lothal narrating the build, not a participant speaking.

import type { ReactNode } from "react";

export function SystemBlock({
  kicker = "Phase",
  children,
}: {
  /** Small uppercase label on the left of the pill. */
  kicker?: string;
  children: ReactNode;
}) {
  return (
    <div
      className="fade-up"
      style={{ display: "flex", justifyContent: "center", margin: "4px 0" }}
    >
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 9,
          padding: "6px 13px",
          borderRadius: 999,
          background: "var(--accent-soft)",
          border:
            "1px solid color-mix(in srgb, var(--accent) 35%, transparent)",
        }}
      >
        <span className="label" style={{ color: "var(--accent-ink)" }}>
          {kicker}
        </span>
        <span style={{ fontSize: 12.5, color: "var(--ink-mute)" }}>
          {children}
        </span>
      </div>
    </div>
  );
}
