// The node's "Implementation" view — the build-side surface: the agent runtime
// stream, sandbox log, code diff, and architecture delta for the branch that
// builds this node.
//
// PLACEHOLDER: the PLAN contract has no agent-runtime / sandbox / diff backing
// yet (that lands with CODE_GENERATION). This renders the full structure with
// representative content so the shape is reviewable, and is clearly marked as a
// preview. Wire it to the real run stream once the backend exposes it.

import { useState } from "react";
import type { PlanNode } from "@/controllers/API/queries/lothal";
import { Icon } from "./atoms";
import { tint } from "./planTheme";

type ImplTab = "agent" | "log" | "diff" | "arch";

const TABS: { id: ImplTab; label: string }[] = [
  { id: "agent", label: "Agent" },
  { id: "log", label: "Log" },
  { id: "diff", label: "Diff" },
  { id: "arch", label: "Architecture delta" },
];

// --- Representative content (illustrative, not live) -----------------------

const AGENT_STEPS = [
  {
    role: "THINKS",
    hue: "#9a8d95",
    text: "Children e1 and e2 are verified; e3 (invalidation) is still in verification. I can wire the seam, but the component gate stays locked until e3 rolls up.",
  },
  {
    role: "EDITS",
    hue: "#d2691e",
    text: "app/lothal/gate.py — compose child verified-flags into the parent roll-up check.",
  },
  {
    role: "EDITS",
    hue: "#d2691e",
    text: "app/lothal/contracts.py — enforce assume ⊆ guarantee compatibility at the seam.",
  },
  {
    role: "RUNS",
    hue: "#5b8dc9",
    text: "pytest -q tests/test_compose.py",
    mono: true,
  },
  { role: "PASS", hue: "#4e9a6a", text: "4 passed in 0.62s" },
  {
    role: "RUNS",
    hue: "#5b8dc9",
    text: "pytest -q tests/test_seam_integration.py",
    mono: true,
  },
  {
    role: "FAIL",
    hue: "#d6584a",
    text: "1 failed — seam test pending e3 contract freeze",
  },
  {
    role: "THINKS",
    hue: "#9a8d95",
    text: "Integration seam depends on e3's invalidation guarantee. Holding in_verification until e3 verifies.",
  },
];

const LOG_LINES = [
  {
    time: "14:02:11",
    level: "info",
    text: "sandbox lothal provisioned (microVM)",
  },
  {
    time: "14:02:48",
    level: "info",
    text: "checked out agent/verification-contracts",
  },
  {
    time: "14:03:30",
    level: "pass",
    text: "tests/test_compose.py ... 4 passed",
  },
  {
    time: "14:04:02",
    level: "fail",
    text: "tests/test_seam_integration.py::test_seam — blocked on e3",
  },
  {
    time: "14:04:03",
    level: "warn",
    text: "roll-up gate: 2/3 children verified — parent held",
  },
];

const LEVEL_COLOR: Record<string, string> = {
  info: "var(--ink-soft)",
  pass: "#4e9a6a",
  fail: "#d6584a",
  warn: "#cf9a3a",
};

const DIFF_FILES = [
  {
    file: "app/lothal/gate.py",
    added: 46,
    removed: 8,
    hunks: [
      {
        header: "@@ -18,9 +18,17 @@ class RollupGate:",
        lines: [
          { t: "ctx", s: "    def can_verify(self, node):" },
          { t: "ctx", s: "        children = node.children()" },
          { t: "del", s: "        return all(c.verified for c in children)" },
          { t: "add", s: "        if any(not c.verified for c in children):" },
          { t: "add", s: '            return Gate.blocked("children", node)' },
          { t: "add", s: "        if not self._integration_passing(node):" },
          {
            t: "add",
            s: '            return Gate.blocked("integration", node)',
          },
          { t: "add", s: "        return Gate.open(node)" },
        ],
      },
    ],
  },
  {
    file: "app/lothal/contracts.py",
    added: 74,
    removed: 14,
    hunks: [
      {
        header: "@@ -5,6 +5,21 @@ def compose(parent, child):",
        lines: [
          {
            t: "ctx",
            s: "    # child guarantees must satisfy parent assumptions",
          },
          {
            t: "add",
            s: "    missing = parent.assumptions - child.guarantees",
          },
          { t: "add", s: "    if missing:" },
          { t: "add", s: "        raise SeamError(missing)" },
          { t: "del", s: "    return True" },
          { t: "add", s: "    return Seam(parent, child)" },
        ],
      },
    ],
  },
];

const DIFF_LINE_STYLE: Record<
  string,
  { bg: string; fg: string; sign: string }
> = {
  add: { bg: tint("#4e9a6a", 12), fg: "var(--ink-90)", sign: "+" },
  del: { bg: tint("#d6584a", 12), fg: "var(--ink-90)", sign: "-" },
  ctx: { bg: "transparent", fg: "var(--ink-mute)", sign: " " },
};

const ARCH_ITEMS = [
  {
    sym: "+",
    hue: "#4e9a6a",
    label: "RollupGate.can_verify composes children + integration",
    detail: "parent verify now gated on child verified-flags and seam tests",
  },
  {
    sym: "~",
    hue: "#cf9a3a",
    label: "contracts.compose enforces assume ⊆ guarantee",
    detail:
      "raises SeamError when a child no longer satisfies the parent contract",
  },
  {
    sym: "→",
    hue: "#d2691e",
    label: "+ derives_from   c2 → c1",
    detail: "verification builds on the node-core state machine",
  },
];

// --- Sub-views ------------------------------------------------------------

function PreviewBanner() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontSize: 11.5,
        color: "var(--ink-mute)",
        background: tint("var(--accent)", 8),
        border: `1px solid ${tint("var(--accent)", 25)}`,
        borderRadius: 9,
        padding: "8px 11px",
        marginBottom: 14,
      }}
    >
      <span
        style={{ color: "var(--accent)", display: "inline-flex", flex: "none" }}
      >
        <Icon.Code size={13} />
      </span>
      <span>
        <b style={{ color: "var(--ink)", fontWeight: 600 }}>Preview</b> — the
        build surface comes alive when this node starts work in code generation.
        The run below is illustrative.
      </span>
    </div>
  );
}

function AgentTab() {
  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 14,
          padding: "9px 14px",
          border: "1px solid var(--border)",
          borderRadius: 11,
          background: "var(--surface)",
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: 999,
            background: "var(--ink-soft)",
            flex: "none",
          }}
        />
        <span style={{ fontSize: 12.5, color: "var(--ink)", fontWeight: 500 }}>
          Agent idle — preview
        </span>
        <span style={{ flex: 1 }} />
        <button
          type="button"
          disabled
          title="Available once the node starts work"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontFamily: "var(--sans)",
            fontSize: 12,
            fontWeight: 600,
            padding: "6px 12px",
            borderRadius: 8,
            border: "1px solid var(--border-strong)",
            background: "transparent",
            color: "var(--ink-soft)",
            cursor: "not-allowed",
            opacity: 0.7,
          }}
        >
          <Icon.Stop size={12} />
          Interrupt
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
        {AGENT_STEPS.map((s, i) => (
          <div
            key={`${s.role}-${i}`}
            style={{ display: "flex", gap: 11, alignItems: "flex-start" }}
          >
            <span
              className="mono"
              style={{
                fontSize: 9,
                fontWeight: 600,
                letterSpacing: "0.05em",
                padding: "4px 8px",
                borderRadius: 6,
                background: tint(s.hue, 15),
                color: s.hue,
                flex: "none",
                width: 62,
                textAlign: "center",
              }}
            >
              {s.role}
            </span>
            <div
              className={s.mono ? "mono" : undefined}
              style={{
                flex: 1,
                fontSize: s.mono ? 12 : 12.5,
                lineHeight: 1.5,
                color: "var(--ink-90)",
                paddingTop: 2,
              }}
            >
              {s.text}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 16,
          border: "1px solid var(--border-strong)",
          borderRadius: 12,
          background: "var(--surface)",
          padding: "11px 12px",
          display: "flex",
          gap: 9,
          alignItems: "flex-end",
          opacity: 0.7,
        }}
      >
        <textarea
          rows={2}
          disabled
          placeholder="Send instructions to the agent — steer it, correct it, or answer a question… (available during code generation)"
          style={{
            flex: 1,
            resize: "none",
            fontFamily: "var(--sans)",
            fontSize: 12.5,
            lineHeight: 1.5,
            color: "var(--ink)",
            background: "var(--paper-deep)",
            border: "1px solid var(--border)",
            borderRadius: 9,
            padding: "9px 11px",
            outline: "none",
          }}
        />
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            fontFamily: "var(--sans)",
            fontSize: 12.5,
            fontWeight: 600,
            height: 38,
            padding: "0 14px",
            borderRadius: 9,
            background: "var(--accent)",
            color: "var(--accent-fg)",
            flex: "none",
          }}
        >
          <Icon.Send size={14} />
          Send
        </span>
      </div>
    </>
  );
}

function LogTab() {
  return (
    <div
      className="mono"
      style={{
        background: "var(--paper-deep)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: "14px 16px",
        fontSize: 12,
        lineHeight: 1.95,
      }}
    >
      {LOG_LINES.map((l, i) => (
        <div key={i} style={{ display: "flex", gap: 12 }}>
          <span style={{ color: "var(--ink-soft)", flex: "none" }}>
            {l.time}
          </span>
          <span
            style={{
              color: LEVEL_COLOR[l.level] ?? "var(--ink-soft)",
              flex: "none",
              width: 42,
              fontWeight: 600,
            }}
          >
            {l.level}
          </span>
          <span style={{ color: "var(--ink-90)" }}>{l.text}</span>
        </div>
      ))}
    </div>
  );
}

function DiffTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {DIFF_FILES.map((f) => (
        <div
          key={f.file}
          style={{
            border: "1px solid var(--border)",
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 14px",
              background: "var(--surface-2)",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span
              style={{
                color: "var(--ink-soft)",
                display: "inline-flex",
                flex: "none",
              }}
            >
              <Icon.File size={13} />
            </span>
            <span
              className="mono"
              style={{ fontSize: 12, color: "var(--ink)", flex: 1 }}
            >
              {f.file}
            </span>
            <span className="mono" style={{ fontSize: 11, color: "#4e9a6a" }}>
              +{f.added}
            </span>
            <span className="mono" style={{ fontSize: 11, color: "#d6584a" }}>
              −{f.removed}
            </span>
          </div>
          <div style={{ background: "var(--paper-deep)", paddingBottom: 4 }}>
            {f.hunks.map((h, hi) => (
              <div key={hi}>
                <div
                  className="mono"
                  style={{
                    fontSize: 11,
                    color: "#5b8dc9",
                    padding: "5px 14px",
                    background: tint("var(--ink)", 6),
                  }}
                >
                  {h.header}
                </div>
                {h.lines.map((ln, li) => {
                  const s = DIFF_LINE_STYLE[ln.t];
                  return (
                    <div
                      key={li}
                      className="mono"
                      style={{
                        display: "flex",
                        fontSize: 11,
                        lineHeight: 1.7,
                        padding: "0 14px",
                        background: s.bg,
                        color: s.fg,
                      }}
                    >
                      <span style={{ width: 12, flex: "none", opacity: 0.65 }}>
                        {s.sign}
                      </span>
                      <span style={{ whiteSpace: "pre-wrap" }}>{ln.s}</span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function ArchTab() {
  const legend = [
    { label: "added", color: "#4e9a6a" },
    { label: "changed", color: "#cf9a3a" },
    { label: "unchanged", color: "#9a8d95" },
  ];
  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "11px 15px",
          border: "1px solid var(--border)",
          borderRadius: 11,
          background: "var(--surface)",
          marginBottom: 14,
        }}
      >
        <span className="label" style={{ color: "var(--ink-mute)" }}>
          Architecture delta
        </span>
        <span style={{ flex: 1 }} />
        {legend.map((l) => (
          <span
            key={l.label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: 11,
              color: "var(--ink-mute)",
            }}
          >
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: 3,
                background: l.color,
              }}
            />
            {l.label}
          </span>
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {ARCH_ITEMS.map((a, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              gap: 11,
              alignItems: "flex-start",
              padding: "12px 14px",
              border: "1px solid var(--border)",
              borderRadius: 11,
              background: "var(--surface)",
            }}
          >
            <span
              className="mono"
              style={{
                width: 22,
                height: 22,
                borderRadius: 6,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 700,
                fontSize: 13,
                background: tint(a.hue, 15),
                color: a.hue,
                flex: "none",
              }}
            >
              {a.sym}
            </span>
            <div style={{ flex: 1 }}>
              <div
                style={{ fontSize: 13, color: "var(--ink)", fontWeight: 500 }}
              >
                {a.label}
              </div>
              <div
                style={{ fontSize: 12, color: "var(--ink-mute)", marginTop: 2 }}
              >
                {a.detail}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Container ------------------------------------------------------------

const slug = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 40) || "node";

export function ImplementationView({ node }: { node: Pick<PlanNode, "name"> }) {
  const [tab, setTab] = useState<ImplTab>("agent");
  const branch = `agent/${slug(node.name)}`;

  return (
    <div>
      <PreviewBanner />

      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 14,
          padding: "14px 18px",
          marginBottom: 14,
          display: "flex",
          alignItems: "center",
          gap: 14,
          flexWrap: "wrap",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "var(--ink-mute)", display: "inline-flex" }}>
            <Icon.Branch size={15} />
          </span>
          <span
            className="mono"
            style={{ fontSize: 12.5, color: "var(--ink)" }}
          >
            {branch}
          </span>
        </span>
        <span style={{ flex: 1 }} />
        <span
          className="mono"
          style={{
            fontSize: 12,
            color: "var(--ink-mute)",
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span>3 files changed</span>
          <span style={{ color: "#4e9a6a" }}>+142</span>
          <span style={{ color: "#d6584a" }}>−28</span>
        </span>
      </div>

      <div
        style={{
          display: "flex",
          gap: 4,
          borderBottom: "1px solid var(--border)",
          marginBottom: 18,
        }}
      >
        {TABS.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              style={{
                fontFamily: "var(--sans)",
                fontSize: 12.5,
                fontWeight: active ? 600 : 400,
                padding: "8px 12px",
                border: "none",
                background: "transparent",
                color: active ? "var(--ink)" : "var(--ink-soft)",
                borderBottom: active
                  ? "2px solid var(--accent)"
                  : "2px solid transparent",
                cursor: "pointer",
                marginBottom: -1,
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "agent" && <AgentTab />}
      {tab === "log" && <LogTab />}
      {tab === "diff" && <DiffTab />}
      {tab === "arch" && <ArchTab />}
    </div>
  );
}
