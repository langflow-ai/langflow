// Small shared PLAN-stage atoms — the visual vocabulary the tree, node detail,
// gate hero, links card, and graph all compose from. Pure presentational; they
// read the maps + helpers in ./planTheme.

import type { CSSProperties } from "react";
import type { PlanNodeKind } from "@/controllers/API/queries/lothal";
import {
  KIND_ABBR,
  KIND_COLOR,
  stateColor,
  stateLabel,
  testStatusColor,
  tint,
  tintedBadge,
} from "./planTheme";

// --- Icons ----------------------------------------------------------------
// Inline strokes inherit `currentColor`, so the parent's `color` tints them.

type IconProps = { size?: number; className?: string };

const stroke = (size: number, extra?: Partial<Record<string, unknown>>) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  ...extra,
});

export const Icon = {
  Lock: ({ size = 12 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  ),
  LockOpen: ({ size = 12 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 7.9-1" />
    </svg>
  ),
  Check: ({ size = 12 }: IconProps) => (
    <svg {...stroke(size, { strokeWidth: 3 })} aria-hidden>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  ),
  X: ({ size = 12 }: IconProps) => (
    <svg {...stroke(size, { strokeWidth: 3 })} aria-hidden>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  ),
  ArrowRight: ({ size = 13 }: IconProps) => (
    <svg {...stroke(size, { strokeWidth: 2.4 })} aria-hidden>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  ),
  Shield: ({ size = 14 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  Warn: ({ size = 13 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h16.9a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      <path d="M12 9v4M12 17h.01" />
    </svg>
  ),
  Graph: ({ size = 12 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <circle cx="5" cy="6" r="2.5" />
      <circle cx="19" cy="6" r="2.5" />
      <circle cx="12" cy="18" r="2.5" />
      <path d="M7 7.5 10.5 16M17 7.5 13.5 16" />
    </svg>
  ),
  Eye: ({ size = 14 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ),
  Code: ({ size = 14 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <path d="m16 18 6-6-6-6M8 6l-6 6 6 6" />
    </svg>
  ),
  Branch: ({ size = 15 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="6" cy="18" r="2.5" />
      <circle cx="18" cy="7" r="2.5" />
      <path d="M6 8.5v7M18 9.5a6 6 0 0 1-6 6H8.5" />
    </svg>
  ),
  File: ({ size = 13 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  ),
  Send: ({ size = 14 }: IconProps) => (
    <svg {...stroke(size)} aria-hidden>
      <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />
    </svg>
  ),
  Stop: ({ size = 12 }: IconProps) => (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
    >
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  ),
};

// --- StateChip ------------------------------------------------------------
// The node lifecycle badge — a tinted pill in the state hue.

export function StateChip({
  state,
  style,
}: {
  state: string;
  style?: CSSProperties;
}) {
  return (
    <span style={{ ...tintedBadge(stateColor(state)), ...style }}>
      {stateLabel(state)}
    </span>
  );
}

// --- TestStatusChip -------------------------------------------------------
// A test run's pass/fail/error/skipped badge — colour-coded off the test status
// palette (NOT the node-lifecycle one).

export function TestStatusChip({
  status,
  style,
}: {
  status: string;
  style?: CSSProperties;
}) {
  return (
    <span style={{ ...tintedBadge(testStatusColor(status)), ...style }}>
      {status}
    </span>
  );
}

// --- MiniBar --------------------------------------------------------------
// A thin progress track (verified-ratio fill). Used by the tree progress hero
// and the per-node roll-up indicator.

export function MiniBar({
  pct,
  width,
  height = 5,
  hue = "var(--state-verified)",
}: {
  pct: number;
  width?: number | string;
  height?: number;
  hue?: string;
}) {
  return (
    <span
      style={{
        width: width ?? "100%",
        height,
        borderRadius: 999,
        background: tint("var(--ink)", 8),
        overflow: "hidden",
        display: "flex",
        flex: width === undefined ? 1 : "none",
      }}
    >
      <span
        style={{
          width: `${Math.max(0, Math.min(100, pct))}%`,
          background: hue,
        }}
      />
    </span>
  );
}

// --- KindTile -------------------------------------------------------------
// The square kind glyph (APP / CMP / EPC / STY) tinted in the kind hue.

export function KindTile({
  kind,
  size = 42,
}: {
  kind: PlanNodeKind;
  size?: number;
}) {
  const hue = KIND_COLOR[kind];
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.26,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: tint(hue, 15),
        color: hue,
        fontFamily: "var(--mono)",
        fontWeight: 700,
        fontSize: size * 0.26,
        letterSpacing: "0.02em",
        flex: "none",
      }}
    >
      {KIND_ABBR[kind]}
    </span>
  );
}

// --- KindDot --------------------------------------------------------------
// The small rounded-square node marker used in tree rows / link rows.

export function KindDot({
  kind,
  size = 7,
}: {
  kind: PlanNodeKind;
  size?: number;
}) {
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.3,
        background: KIND_COLOR[kind],
        flex: "none",
      }}
    />
  );
}
