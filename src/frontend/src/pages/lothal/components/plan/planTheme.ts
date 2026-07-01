// Shared PLAN-stage design maps + style helpers. Ported faithfully from the
// internal Lothal reference mockup so the customer-facing PLAN UI speaks one
// badge / colour language across the tree, the node detail, and the graph.
//
// Pure data + CSSProperties helpers — no React here. The JSX atoms that consume
// these maps (StateChip, MiniBar, KindTile, …) live in ./atoms.

import type { CSSProperties } from "react";
import type {
  PlanLinkType,
  PlanNodeKind,
} from "@/controllers/API/queries/lothal";

// The node lifecycle, in order. `state` is a free string on the wire, so the UI
// owns the ordering (the PM service may surface a state we render as "unknown").
export const STATE_ORDER = [
  "draft",
  "ratified",
  "in_progress",
  "in_verification",
  "verified",
] as const;

// Per-state hue. Backed by `--state-*` tokens (defined in lothal-theme.css) so
// they adapt with the theme like `--success`/`--warn` already do. `draft` has no
// colour of its own (→ --ink-soft); `failed` and `invalidated` get distinct hues
// (the previous UI collapsed both into one rust).
export const STATE_COLOR: Record<string, string> = {
  draft: "var(--state-draft)",
  ratified: "var(--state-ratified)",
  in_progress: "var(--state-in-progress)",
  in_verification: "var(--state-in-verification)",
  verified: "var(--state-verified)",
  failed: "var(--state-failed)",
  invalidated: "var(--state-invalidated)",
};

export const STATE_LABEL: Record<string, string> = {
  draft: "Draft",
  ratified: "Ratified",
  in_progress: "In progress",
  in_verification: "In verification",
  verified: "Verified",
  failed: "Failed",
  invalidated: "Invalidated",
};

export const stateColor = (s: string): string =>
  STATE_COLOR[s] ?? "var(--ink-mute)";
export const stateLabel = (s: string): string =>
  STATE_LABEL[s] ?? s.replace(/_/g, " ");

// Test run status → hue. Distinct from the node lifecycle: a test is
// passed/failed/error/skipped (PlanTest.latest_status), NOT a node state, so it
// must not borrow STATE_COLOR (where only "failed" happens to exist).
export const TEST_STATUS_COLOR: Record<string, string> = {
  passed: "var(--state-verified)",
  failed: "var(--state-failed)",
  error: "var(--state-failed)",
  skipped: "var(--ink-soft)",
};
export const testStatusColor = (s: string): string =>
  TEST_STATUS_COLOR[s] ?? "var(--ink-mute)";

// Node kind → label / abbreviation / hue (reference KIND map).
export const KIND_LABEL: Record<PlanNodeKind, string> = {
  app: "App",
  component: "Component",
  epic: "Epic",
  story: "Story",
};
export const KIND_ABBR: Record<PlanNodeKind, string> = {
  app: "APP",
  component: "CMP",
  epic: "EPC",
  story: "STY",
};
export const KIND_COLOR: Record<PlanNodeKind, string> = {
  app: "#e95420",
  component: "#5b8dc9",
  epic: "#c074b0",
  story: "#4e9a6a",
};

// Typed link → colour, dash pattern, and whether it is the invalidation channel
// (reference LINK map). `derives_from` is the one that ripples re-ratification.
export type LinkTypeMeta = {
  color: string;
  dash: string;
  invalidation: boolean;
};
export const LINKTYPE_META: Record<string, LinkTypeMeta> = {
  derives_from: { color: "#d2691e", dash: "none", invalidation: true },
  blocks: { color: "#cf5a47", dash: "none", invalidation: false },
  blocked_by: { color: "#cf5a47", dash: "4 3", invalidation: false },
  relates_to: { color: "#9a8d95", dash: "2 3", invalidation: false },
  verifies: { color: "#5b8dc9", dash: "none", invalidation: false },
};
export const linkMeta = (t: string): LinkTypeMeta =>
  LINKTYPE_META[t] ?? {
    color: "var(--ink-mute)",
    dash: "none",
    invalidation: false,
  };

export const LINK_TYPES: PlanLinkType[] = [
  "derives_from",
  "blocks",
  "blocked_by",
  "relates_to",
  "verifies",
];

// Allowed transitions out of each state (reference ALLOWED map). The transition
// endpoint accepts any target; this is what gates which buttons we surface.
export const ALLOWED_TRANSITIONS: Record<string, string[]> = {
  draft: ["ratified"],
  ratified: ["in_progress", "invalidated"],
  in_progress: ["in_verification", "failed"],
  in_verification: ["verified", "failed"],
  verified: ["invalidated"],
  failed: ["in_progress"],
  invalidated: ["draft"],
};
export const allowedTransitions = (s: string): string[] =>
  ALLOWED_TRANSITIONS[s] ?? [];

// Per-state guard copy shown under the node stepper (reference GUARD notes).
export const GUARDS: Record<string, { title: string; note: string }> = {
  draft: {
    title: "Open",
    note: "the contract and criteria stay editable until you ratify and freeze them.",
  },
  ratified: {
    title: "Frozen",
    note: "the assume-guarantee contract is sealed — start work to build against it.",
  },
  in_progress: {
    title: "Building",
    note: "work proceeds against the frozen contract; move to verification once the tests are ready.",
  },
  in_verification: {
    title: "Roll-up gate",
    note: "this node verifies only when its own tests pass AND every child is verified AND its integration tests pass.",
  },
  verified: {
    title: "Sealed",
    note: "parents now trust only its contract; internals are not re-tested. A dependency change can invalidate it.",
  },
  failed: {
    title: "Blocked",
    note: "verification failed — reopen to in progress to fix and retry.",
  },
  invalidated: {
    title: "Stale",
    note: "an upstream guarantee changed; reopen to draft to reconcile the contract.",
  },
};
export const guardOf = (s: string): { title: string; note: string } =>
  GUARDS[s] ?? { title: stateLabel(s), note: "" };

// A colour mixed toward transparent — the tint primitive the reference uses for
// every soft fill (`color-mix` is supported across our target browsers).
export const tint = (hue: string, pct: number): string =>
  `color-mix(in srgb, ${hue} ${pct}%, transparent)`;

// The reference `badge()` treatment: a 15%-tinted fill + tinted border in the
// hue. One source of truth so status, kind, scope, link-type and event chips all
// share the same badge language.
export function tintedBadge(hue: string): CSSProperties {
  return {
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.03em",
    textTransform: "uppercase",
    color: hue,
    background: tint(hue, 15),
    border: `1px solid ${tint(hue, 35)}`,
    borderRadius: 6,
    padding: "2px 7px",
    whiteSpace: "nowrap",
    lineHeight: 1.4,
  };
}

// Verified ratio over a node list — drives the tree progress hero and roll-up
// bars. Returns { verified, total, pct } with pct rounded to a whole number.
export function verifiedRatio(states: string[]): {
  verified: number;
  total: number;
  pct: number;
} {
  const total = states.length;
  const verified = states.filter((s) => s === "verified").length;
  const pct = total ? Math.round((verified / total) * 100) : 0;
  return { verified, total, pct };
}
