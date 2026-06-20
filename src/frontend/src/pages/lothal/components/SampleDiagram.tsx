// A lightweight, presentational sequence-diagram illustration (Epic D.15).
//
// The live workspace canvas is <D2Canvas>: it displays an SVG the backend renders
// from the project's D2 source. But the Landing and Design-System pages only need
// a *decorative* sample — they have no project and no backend round-trip. The old
// xyflow <DiagramCanvas> filled that role; with the xyflow canvas removed (D.15)
// this draws the same idea — a sequence diagram: participants across the top, each
// with a lifeline, and ordered messages between them — as a small, theme-aware
// static SVG (CSS variables, so it tracks light/dark). No @xyflow/react, no D2
// compiler, no embedded fonts; purely cosmetic.

export type SampleParticipant = { id: string; label: string };
export type SampleMessage = {
  from: string;
  to: string;
  label: string;
  /** Dashed line — an async message or a reply/return (matches D2's `-->`). */
  dashed?: boolean;
};

const COL_WIDTH = 150;
const HEAD_HEIGHT = 34;
const ROW_HEIGHT = 44;
const TOP_PAD = 12;
const SIDE_PAD = 24;
const HEAD_GAP = 18; // space between the participant heads and the first message

export function SampleDiagram({
  participants,
  messages,
  title,
}: {
  participants: SampleParticipant[];
  messages: SampleMessage[];
  /** Accessible name for the figure. */
  title?: string;
}) {
  const colX = (id: string) => {
    const idx = participants.findIndex((p) => p.id === id);
    const i = idx < 0 ? 0 : idx;
    return SIDE_PAD + COL_WIDTH / 2 + i * COL_WIDTH;
  };

  const width = SIDE_PAD * 2 + COL_WIDTH * Math.max(participants.length, 1);
  const firstRowY = TOP_PAD + HEAD_HEIGHT + HEAD_GAP;
  const height = firstRowY + ROW_HEIGHT * messages.length + TOP_PAD;
  const lifelineBottom = height - TOP_PAD;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={title ?? "Sequence diagram preview"}
      style={{ display: "block", maxHeight: "100%" }}
    >
      <defs>
        <marker
          id="sample-diagram-arrow"
          viewBox="0 0 8 8"
          refX="7"
          refY="4"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L8 4 L0 8 z" fill="var(--ink-soft, #888)" />
        </marker>
      </defs>

      {/* Lifelines + participant heads */}
      {participants.map((p) => {
        const x = colX(p.id);
        return (
          <g key={p.id}>
            <line
              x1={x}
              y1={TOP_PAD + HEAD_HEIGHT}
              x2={x}
              y2={lifelineBottom}
              stroke="var(--border, #ccc)"
              strokeWidth="1"
              strokeDasharray="3 4"
            />
            <rect
              x={x - COL_WIDTH / 2 + 8}
              y={TOP_PAD}
              width={COL_WIDTH - 16}
              height={HEAD_HEIGHT}
              rx="7"
              fill="var(--surface, #fff)"
              stroke="var(--border, #ccc)"
              strokeWidth="1"
            />
            <text
              x={x}
              y={TOP_PAD + HEAD_HEIGHT / 2}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize="12"
              fontWeight="600"
              fill="var(--ink, #222)"
            >
              {p.label}
            </text>
          </g>
        );
      })}

      {/* Ordered messages */}
      {messages.map((m, i) => {
        const y = firstRowY + ROW_HEIGHT * i + ROW_HEIGHT / 2;
        const x1 = colX(m.from);
        const x2 = colX(m.to);
        const labelX = (x1 + x2) / 2;
        return (
          <g key={`${m.from}-${m.to}-${i}`}>
            <text
              x={labelX}
              y={y - 8}
              textAnchor="middle"
              fontSize="10.5"
              fill="var(--ink-mute, #555)"
            >
              {`${i + 1}. ${m.label}`}
            </text>
            <line
              x1={x1}
              y1={y}
              x2={x2}
              y2={y}
              stroke="var(--ink-soft, #888)"
              strokeWidth="1.5"
              strokeDasharray={m.dashed ? "5 4" : undefined}
              markerEnd="url(#sample-diagram-arrow)"
            />
          </g>
        );
      })}
    </svg>
  );
}
