// Phase-aware status dot with a soft glow ring and a verb label.
// Pulses while in progress; steady once delivered.

const MAP: Record<string, { color: string; label: string }> = {
  CLARIFICATION: { color: "var(--accent)", label: "clarifying" },
  // Epic E.2 merged the sketch + refine phases into one ARCHITECTURE stage.
  ARCHITECTURE: { color: "#3e7ab8", label: "designing" },
  CODE_GENERATION: { color: "#c08a2e", label: "generating" },
  DONE: { color: "var(--success)", label: "delivered" },
};

export function StatusDot({ phase }: { phase: string }) {
  const m = MAP[phase] ?? MAP.CLARIFICATION;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 12,
        color: "var(--ink-mute)",
      }}
    >
      <span
        className={phase !== "DONE" ? "pulse" : ""}
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: m.color,
          // color-mix gives a valid translucent ring for both var() and hex
          // colors (the design's `${color}22` is invalid for var() colors).
          boxShadow: `0 0 0 3px color-mix(in srgb, ${m.color} 13%, transparent)`,
        }}
      />
      <span style={{ fontSize: 11.5, letterSpacing: "0.02em" }}>{m.label}</span>
    </span>
  );
}
