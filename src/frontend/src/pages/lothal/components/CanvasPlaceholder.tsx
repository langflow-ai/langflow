// The right pane before a diagram exists. The live diagram surface is <D2Canvas>
// (Epic D.6); until a project has D2 to show, this is the honest placeholder — a
// faint sequence-diagram glyph and a phase-aware line about what's coming. Shown
// during CLARIFICATION (no diagram yet); other phases get a neutral fallback.

const COPY: Record<string, { title: string; sub: string }> = {
  CLARIFICATION: {
    title: "The diagram takes shape here",
    sub: "Once we've clarified what you're building, Lothal designs the architecture on this canvas.",
  },
  // Epic E.2 merged generation + refinement into the single ARCHITECTURE stage.
  ARCHITECTURE: {
    title: "Designing the architecture",
    sub: "Lothal is drafting the architecture from your brief.",
  },
};

const FALLBACK = {
  title: "Nothing on the canvas yet",
  sub: "The diagram appears here as the build progresses.",
};

function DiagramGlyph() {
  return (
    <svg
      width="120"
      height="92"
      viewBox="0 0 120 92"
      fill="none"
      stroke="currentColor"
      aria-hidden
    >
      {/* two participants */}
      <rect x="14" y="6" width="34" height="18" rx="4" strokeWidth="1.4" />
      <rect x="72" y="6" width="34" height="18" rx="4" strokeWidth="1.4" />
      {/* lifelines */}
      <line
        x1="31"
        y1="24"
        x2="31"
        y2="86"
        strokeWidth="1.2"
        strokeDasharray="3 4"
      />
      <line
        x1="89"
        y1="24"
        x2="89"
        y2="86"
        strokeWidth="1.2"
        strokeDasharray="3 4"
      />
      {/* messages */}
      <path
        d="M31 40h58M83 40l6-3M83 40l6 3"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M89 60H31M37 60l-6-3M37 60l-6 3"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CanvasPlaceholder({ phase }: { phase: string }) {
  const copy = COPY[phase] ?? FALLBACK;
  return (
    <div
      style={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        padding: 40,
        textAlign: "center",
      }}
    >
      <div style={{ color: "var(--ink-faint)" }}>
        <DiagramGlyph />
      </div>
      <div
        className="serif"
        style={{ fontSize: 24, color: "var(--ink-mute)", fontStyle: "italic" }}
      >
        {copy.title}
      </div>
      <div
        style={{
          fontSize: 13,
          lineHeight: 1.55,
          color: "var(--ink-soft)",
          maxWidth: 340,
        }}
      >
        {copy.sub}
      </div>
    </div>
  );
}
