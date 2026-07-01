// Lothal landing page (Epic 0.5) — the public front door at "/". The marketing
// surface, reframed for a developer / technical-founder audience as a "trust
// ladder": the emotion it answers is a skeptical engineer's distrust of AI
// codegen, so the page argues that Lothal is disciplined software engineering
// ACCELERATED by AI — with the discipline enforced, not optional. Running order:
// sticky blur nav, hero (early-access pill + live preview), the reframe band
// (name the problem), an honest phase ribbon (Generate/Deliver are not built yet
// → tagged "coming"), then the ladder — Clarify, Architecture (risk-ordered),
// the enforced-validation gate (flagship 1), the contract/dependency tree
// (flagship 2, the visual centerpiece), git-per-node + traceability, delivery,
// a "pay for verified work" trust line, the closing CTA, and the footer.
// The page's only actions are Log in and Sign up; /lothal lives behind auth.

import { type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  isCodePhase,
  LOTHAL_VERSION,
  LothalMark,
  PHASES,
  SampleDiagram,
  type SampleMessage,
  type SampleParticipant,
} from "../components";
import { LothalSurface } from "../theme/LothalSurface";

const SECTION_IDS = {
  how: "lothal-how",
  gate: "lothal-gate",
  tree: "lothal-tree",
  deliver: "lothal-deliver",
} as const;

// --- The sample project ("larder") ---------------------------------------------
// The same mini system used across the app's mocks, drawn as a sequence diagram
// (the product's real Design output, Epic D): a customer submits an order, the
// order service reserves stock, inventory reports back, the kitchen board pings
// the customer. Decorative — <SampleDiagram> is a static illustration.

const LARDER_PARTICIPANTS: SampleParticipant[] = [
  { id: "customer", label: "Customer" },
  { id: "order", label: "Order Service" },
  { id: "inventory", label: "Inventory" },
  { id: "kitchen", label: "Kitchen Board" },
];

const LARDER_MESSAGES: SampleMessage[] = [
  { from: "customer", to: "order", label: "submit order" },
  { from: "order", to: "inventory", label: "reserve stock" },
  { from: "inventory", to: "kitchen", label: "stock status", dashed: true },
  { from: "kitchen", to: "customer", label: "ready for pickup", dashed: true },
];

// --- Hero product preview -------------------------------------------------------

/** The hero preview's left pane: the larder project mid-clarification. */
function SceneChat() {
  return (
    <div
      style={{
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        background: "var(--paper)",
        minWidth: 0,
      }}
    >
      <div
        style={{
          padding: "11px 16px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <span className="label">Conversation</span>
      </div>
      <div
        style={{
          flex: 1,
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 14,
          textAlign: "left",
        }}
      >
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <div
            style={{
              maxWidth: "88%",
              padding: "8px 12px",
              fontSize: 12.5,
              lineHeight: 1.5,
              background: "var(--ink)",
              color: "var(--paper)",
              borderRadius: "11px 11px 3px 11px",
            }}
          >
            A tool to track bakery inventory and the week's orders.
          </div>
        </div>
        <div style={{ display: "flex", gap: 9, alignItems: "flex-start" }}>
          <span
            style={{
              width: 24,
              height: 24,
              borderRadius: 6,
              flexShrink: 0,
              background: "var(--accent-soft)",
              color: "var(--accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <LothalMark size={13} />
          </span>
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            <div
              className="serif"
              style={{
                fontSize: 14.5,
                lineHeight: 1.5,
                color: "var(--ink-90)",
              }}
            >
              Who places orders, and how do they reach you?
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(
                [
                  ["Walk-ins", "in person"],
                  ["Phone & text", "manual"],
                  ["Phone + a webpage", "mixed"],
                ] as const
              ).map(([l, h], i) => (
                <span
                  key={l}
                  style={{
                    display: "inline-flex",
                    alignItems: "baseline",
                    gap: 6,
                    padding: "5px 9px",
                    borderRadius: 7,
                    fontSize: 11.5,
                    border: `1px solid ${i === 2 ? "var(--accent)" : "var(--border-strong)"}`,
                    background:
                      i === 2 ? "var(--accent-soft)" : "var(--surface)",
                    color: i === 2 ? "var(--accent-ink)" : "var(--ink)",
                  }}
                >
                  {l}
                  <span
                    className="mono"
                    style={{ fontSize: 9.5, color: "var(--ink-soft)" }}
                  >
                    {h}
                  </span>
                </span>
              ))}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 9, alignItems: "flex-start" }}>
          <span
            style={{
              width: 24,
              height: 24,
              borderRadius: 6,
              flexShrink: 0,
              background: "var(--accent-soft)",
              color: "var(--accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <LothalMark size={13} />
          </span>
          <div
            className="serif"
            style={{ fontSize: 14.5, lineHeight: 1.5, color: "var(--ink-90)" }}
          >
            That's enough to draft a sequence diagram.
          </div>
        </div>
      </div>
      <div style={{ padding: 14, borderTop: "1px solid var(--border)" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 10px",
            borderRadius: 10,
            border: "1px solid var(--border-strong)",
            background: "var(--surface)",
            fontSize: 12,
            color: "var(--ink-soft)",
          }}
        >
          <span
            style={{ display: "inline-flex", alignItems: "center", gap: 1 }}
          >
            <span className="caret" aria-hidden />
            <span>Type your answer…</span>
          </span>
          <span className="mono" style={{ fontSize: 10.5 }}>
            ↵
          </span>
        </div>
      </div>
    </div>
  );
}

/** The hero's windowed product preview: chat beside a live diagram canvas. */
function HeroScene() {
  return (
    <div
      style={{
        position: "relative",
        borderRadius: 16,
        border: "1px solid var(--border-strong)",
        background: "var(--paper-deep)",
        boxShadow: "0 40px 90px -40px rgba(0,0,0,.55), 0 0 0 1px var(--border)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "11px 14px",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
        }}
      >
        <span style={{ display: "flex", gap: 7 }} aria-hidden>
          {["#e0654a", "#d9a441", "#5a9c63"].map((c) => (
            <span
              key={c}
              style={{
                width: 11,
                height: 11,
                borderRadius: "50%",
                background: c,
                opacity: 0.85,
              }}
            />
          ))}
        </span>
        <div
          className="mono"
          style={{
            margin: "0 auto",
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "3px 12px",
            borderRadius: 7,
            background: "var(--paper)",
            border: "1px solid var(--border)",
            fontSize: 11.5,
            color: "var(--ink-soft)",
          }}
        >
          <LothalMark size={12} /> lothal.app / larder
        </div>
        <span style={{ width: 56 }} />
      </div>

      <div
        className="land-hero-split"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 0.78fr) 1fr",
          minHeight: 384,
        }}
      >
        <SceneChat />
        <div style={{ position: "relative", minHeight: 280, minWidth: 0 }}>
          <div
            style={{
              position: "absolute",
              top: 11,
              left: 16,
              display: "flex",
              gap: 8,
              alignItems: "center",
              zIndex: 5,
            }}
          >
            <span className="label">Design</span>
            <span
              className="mono"
              style={{ fontSize: 10, color: "var(--ink-faint)" }}
            >
              {LARDER_PARTICIPANTS.length} participants ·{" "}
              {LARDER_MESSAGES.length} messages
            </span>
          </div>
          <div style={{ position: "absolute", inset: 0, padding: 16 }}>
            <SampleDiagram
              participants={LARDER_PARTICIPANTS}
              messages={LARDER_MESSAGES}
              title="Sample sequence diagram: a bakery order flow"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Section head + shared bits --------------------------------------------------

/** Eyebrow + serif title + optional sub, centered or left-aligned. */
function SectionHead({
  eyebrow,
  title,
  sub,
  align = "center",
}: {
  eyebrow: string;
  title: ReactNode;
  sub?: string;
  align?: "center" | "left";
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        alignItems: align === "center" ? "center" : "flex-start",
        textAlign: align === "center" ? "center" : "left",
        maxWidth: align === "center" ? 660 : "none",
        margin: align === "center" ? "0 auto" : 0,
      }}
    >
      <span className="label" style={{ color: "var(--accent)" }}>
        {eyebrow}
      </span>
      <h2
        className="serif"
        style={{
          fontSize: "clamp(28px, 3.4vw, 40px)",
          lineHeight: 1.16,
          letterSpacing: "-0.015em",
          color: "var(--ink)",
        }}
      >
        {title}
      </h2>
      {sub && (
        <p
          style={{
            fontSize: 15.5,
            lineHeight: 1.6,
            color: "var(--ink-mute)",
            margin: 0,
          }}
        >
          {sub}
        </p>
      )}
    </div>
  );
}

/** A small "Coming next" chip — the honesty marker for code-generation features
 *  that aren't live yet, matching the phase-ribbon's treatment. */
function ComingChip() {
  return (
    <span
      className="mono"
      style={{
        fontSize: 10.5,
        color: "var(--ink-faint)",
        border: "1px solid var(--border)",
        borderRadius: 999,
        padding: "2px 9px",
        whiteSpace: "nowrap",
      }}
    >
      Coming next
    </span>
  );
}

/** A two-column feature row: copy (eyebrow/title/body/bullets) beside a visual.
 *  `flip` puts the visual on the left; used to alternate the ladder's rhythm. */
function FeatureRow({
  eyebrow,
  title,
  body,
  bullets,
  aside,
  coming,
  visual,
  flip,
}: {
  eyebrow: string;
  title: ReactNode;
  body: ReactNode;
  bullets?: string[];
  aside?: string;
  coming?: boolean;
  visual: ReactNode;
  flip?: boolean;
}) {
  const copy = (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <span className="label" style={{ color: "var(--accent)" }}>
          {eyebrow}
        </span>
        {coming && <ComingChip />}
      </span>
      <h2
        className="serif"
        style={{
          fontSize: "clamp(26px, 3vw, 36px)",
          lineHeight: 1.18,
          letterSpacing: "-0.015em",
          color: "var(--ink)",
          margin: 0,
        }}
      >
        {title}
      </h2>
      <p
        style={{
          fontSize: 15.5,
          lineHeight: 1.7,
          color: "var(--ink-mute)",
          margin: 0,
          maxWidth: 540,
        }}
      >
        {body}
      </p>
      {bullets && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {bullets.map((b) => (
            <div
              key={b}
              style={{ display: "flex", alignItems: "flex-start", gap: 10 }}
            >
              <span
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: 5,
                  flexShrink: 0,
                  marginTop: 1,
                  background: "var(--accent-soft)",
                  color: "var(--accent)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                }}
              >
                ✓
              </span>
              <span
                style={{
                  fontSize: 14.5,
                  color: "var(--ink-90)",
                  lineHeight: 1.5,
                }}
              >
                {b}
              </span>
            </div>
          ))}
        </div>
      )}
      {aside && (
        <p
          style={{
            fontSize: 13,
            lineHeight: 1.6,
            color: "var(--ink-soft)",
            margin: 0,
            paddingLeft: 12,
            borderLeft: "2px solid var(--border-strong)",
            maxWidth: 520,
          }}
        >
          {aside}
        </p>
      )}
    </div>
  );
  return (
    <div
      className="land-feature"
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 48,
        alignItems: "center",
      }}
    >
      {flip ? (
        <>
          <div className="land-feature-visual">{visual}</div>
          {copy}
        </>
      ) : (
        <>
          {copy}
          <div className="land-feature-visual">{visual}</div>
        </>
      )}
    </div>
  );
}

// --- Scene: the enforced gate (flagship 1) ---------------------------------------

const chip = (text: string, hue: string) => (
  <span
    className="mono"
    style={{
      fontSize: 9.5,
      fontWeight: 600,
      textTransform: "uppercase",
      letterSpacing: "0.04em",
      color: hue,
      background: `color-mix(in srgb, ${hue} 15%, transparent)`,
      border: `1px solid color-mix(in srgb, ${hue} 35%, transparent)`,
      borderRadius: 5,
      padding: "2px 7px",
      whiteSpace: "nowrap",
    }}
  >
    {text}
  </span>
);

const GREEN = "#4e9a6a";
const AMBER = "#c9903a";

/** The gate visual: a node's acceptance criteria, each either covered by a
 *  passing test or — for the uncovered one — rejected, blocking "verified". */
function GateScene() {
  const criteria: Array<{ text: string; test: string | null }> = [
    { text: "Rejects expired or unknown codes", test: "unit · pass" },
    { text: "Applies at most one discount per order", test: "unit · pass" },
    {
      text: "Recomputes the order total server-side",
      test: "integration · pass",
    },
    { text: "Reflects the discount in the receipt", test: null },
  ];
  const covered = criteria.filter((c) => c.test).length;
  return (
    <div
      style={{
        borderRadius: 14,
        border: "1px solid var(--border-strong)",
        background: "var(--paper)",
        overflow: "hidden",
        boxShadow: "0 30px 70px -40px rgba(0,0,0,.5)",
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <span className="label">Definition of done</span>
        <span
          className="mono"
          style={{ fontSize: 10, color: "var(--ink-faint)" }}
        >
          enforced
        </span>
      </div>
      <div
        style={{
          padding: 18,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          {chip("story", GREEN)}
          <span className="serif" style={{ fontSize: 17, color: "var(--ink)" }}>
            Apply a discount code at checkout
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {criteria.map((c) => {
            const ok = !!c.test;
            const hue = ok ? GREEN : "#c05b52";
            return (
              <div
                key={c.text}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "9px 11px",
                  borderRadius: 9,
                  background: "var(--surface)",
                  border: `1px solid color-mix(in srgb, ${hue} 28%, var(--border))`,
                }}
              >
                <span
                  style={{
                    width: 17,
                    height: 17,
                    borderRadius: 5,
                    flex: "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    color: "#fff",
                    background: hue,
                  }}
                >
                  {ok ? "✓" : "✕"}
                </span>
                <span
                  style={{ flex: 1, fontSize: 12.5, color: "var(--ink-90)" }}
                >
                  {c.text}
                </span>
                {ok ? (
                  <span
                    className="mono"
                    style={{ fontSize: 9.5, color: "var(--ink-soft)" }}
                  >
                    {c.test}
                  </span>
                ) : (
                  chip("no test — rejected", "#c05b52")
                )}
              </div>
            );
          })}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            padding: "10px 12px",
            borderRadius: 9,
            background: "color-mix(in srgb, #c05b52 10%, transparent)",
            border: "1px solid color-mix(in srgb, #c05b52 32%, transparent)",
          }}
        >
          <span style={{ fontSize: 12.5, color: "var(--ink-90)" }}>
            {covered} of {criteria.length} criteria covered — can't be verified.
          </span>
          <span
            className="mono"
            style={{ fontSize: 10.5, color: "#c05b52", fontWeight: 600 }}
          >
            blocked
          </span>
        </div>
      </div>
    </div>
  );
}

// --- Scene: the contract / dependency tree (flagship 2 — the centerpiece) ---------

/** The showstopper visual: a live dependency tree of contracts. One node's
 *  contract just changed (amber); everything downstream is flagged to re-verify
 *  in a click, while independent branches still hold. "No surprises." */
function ContractTreeScene() {
  // Fixed layout on a small grid so the connectors line up crisply.
  const W = 176;
  const node = (
    x: number,
    y: number,
    label: string,
    kind: string,
    state: "changed" | "reverify" | "holds",
  ) => {
    const map = {
      changed: { hue: AMBER, tag: "contract changed" },
      reverify: { hue: AMBER, tag: "re-verify" },
      holds: { hue: GREEN, tag: "holds" },
    } as const;
    const { hue, tag } = map[state];
    const dashed = state === "reverify";
    return (
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          width: W,
          boxSizing: "border-box",
          padding: "9px 11px",
          borderRadius: 10,
          background: "var(--surface)",
          border: `1.5px ${dashed ? "dashed" : "solid"} color-mix(in srgb, ${hue} ${state === "holds" ? 40 : 70}%, var(--border))`,
          boxShadow:
            state === "changed"
              ? `0 0 0 3px color-mix(in srgb, ${hue} 22%, transparent)`
              : "none",
          zIndex: 2,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            className="mono"
            style={{ fontSize: 8.5, color: "var(--ink-soft)" }}
          >
            {kind}
          </span>
          <span
            className="mono"
            style={{
              marginLeft: "auto",
              fontSize: 8.5,
              fontWeight: 600,
              color: hue,
            }}
          >
            {tag}
          </span>
        </div>
        <div style={{ fontSize: 12.5, color: "var(--ink)", marginTop: 2 }}>
          {label}
        </div>
      </div>
    );
  };

  return (
    <div
      style={{
        borderRadius: 16,
        border: "1px solid var(--border-strong)",
        background: "var(--paper)",
        overflow: "hidden",
        boxShadow: "0 40px 90px -44px rgba(0,0,0,.55)",
      }}
    >
      <div
        style={{
          padding: "11px 16px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <span className="label">Dependency tree</span>
        <span
          className="mono"
          style={{ fontSize: 10, color: "var(--ink-faint)" }}
        >
          contracts · live
        </span>
        <span
          className="mono"
          style={{
            marginLeft: "auto",
            fontSize: 10,
            color: AMBER,
            border: `1px solid color-mix(in srgb, ${AMBER} 45%, transparent)`,
            borderRadius: 999,
            padding: "3px 10px",
          }}
        >
          ↻ Re-verify downstream
        </span>
      </div>

      <div style={{ position: "relative", height: 320, padding: "8px 12px" }}>
        {/* connectors */}
        <svg
          width="100%"
          height="100%"
          style={{ position: "absolute", inset: 0, zIndex: 1 }}
          aria-hidden
          preserveAspectRatio="none"
        >
          <title>Contract dependency edges</title>
          {/* Checkout → Cart / Discounts / Payment */}
          <path
            d="M108,74 C108,104 96,104 96,132"
            fill="none"
            stroke="var(--border-strong)"
            strokeWidth="1.5"
          />
          <path
            d="M150,74 C220,104 250,104 250,132"
            fill="none"
            stroke={`color-mix(in srgb, ${AMBER} 60%, transparent)`}
            strokeWidth="1.5"
          />
          <path
            d="M170,74 C360,104 404,104 404,132"
            fill="none"
            stroke="var(--border-strong)"
            strokeWidth="1.5"
          />
          {/* Discounts → Order total (downstream, amber dashed) */}
          <path
            d="M262,178 C262,208 250,208 250,238"
            fill="none"
            stroke={`color-mix(in srgb, ${AMBER} 70%, transparent)`}
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
          {/* Payment → Order total (downstream, amber dashed) */}
          <path
            d="M404,178 C404,208 300,208 300,238"
            fill="none"
            stroke={`color-mix(in srgb, ${AMBER} 70%, transparent)`}
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
        </svg>

        {node(70, 34, "Checkout", "app", "holds")}
        {node(8, 132, "Cart", "component", "holds")}
        {node(174, 132, "Discounts", "component", "changed")}
        {node(316, 132, "Payment", "component", "reverify")}
        {node(174, 238, "Order total", "story", "reverify")}
      </div>

      <div
        style={{
          padding: "11px 16px",
          borderTop: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
          fontSize: 11.5,
          color: "var(--ink-soft)",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: 3,
              background: `color-mix(in srgb, ${AMBER} 70%, transparent)`,
            }}
          />
          2 nodes need re-ratifying against the new contract
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: 3,
              background: `color-mix(in srgb, ${GREEN} 70%, transparent)`,
            }}
          />
          Cart is unaffected — it still holds
        </span>
      </div>
    </div>
  );
}

// --- Scene: git-per-node + traceability ------------------------------------------

/** Two stacked panels: automatic git (each finished node = a commit) above a
 *  trace that walks a line of code back to the decisions that produced it. */
function GitTraceScene() {
  const commits = [
    { msg: "feat: discount code validation", sha: "a1b2c3d", done: true },
    { msg: "feat: cart totals recompute", sha: "c3d4e5f", done: true },
    { msg: "feat: server-side receipt render", sha: "9f8e7d6", done: false },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div
        style={{
          borderRadius: 12,
          border: "1px solid var(--border-strong)",
          background: "var(--paper)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "9px 13px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span className="label">History</span>
          <span
            className="mono"
            style={{ fontSize: 10, color: "var(--ink-faint)" }}
          >
            one commit per node
          </span>
        </div>
        <div style={{ padding: "6px 0" }}>
          {commits.map((c) => (
            <div
              key={c.sha}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "7px 13px",
              }}
            >
              <span
                style={{
                  width: 15,
                  height: 15,
                  borderRadius: "50%",
                  flex: "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 9,
                  color: "#fff",
                  background: c.done ? GREEN : "var(--ink-faint)",
                }}
              >
                {c.done ? "✓" : "…"}
              </span>
              <span
                className="mono"
                style={{ fontSize: 11.5, color: "var(--ink-90)", flex: 1 }}
              >
                {c.msg}
              </span>
              <span
                className="mono"
                style={{ fontSize: 10.5, color: "var(--ink-soft)" }}
              >
                {c.sha}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div
        style={{
          borderRadius: 12,
          border: "1px solid var(--border-strong)",
          background: "var(--paper)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "9px 13px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span className="label">Trace</span>
          <span
            className="mono"
            style={{ fontSize: 10, color: "var(--ink-faint)" }}
          >
            why this line exists
          </span>
        </div>
        <div style={{ padding: 13 }}>
          <div
            className="mono"
            style={{
              fontSize: 11,
              color: "var(--ink-90)",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 7,
              padding: "8px 10px",
              lineHeight: 1.7,
            }}
          >
            <span style={{ color: "var(--ink-faint)" }}>if </span>
            <span
              style={{
                background:
                  "color-mix(in srgb, var(--accent) 22%, transparent)",
                borderRadius: 3,
                padding: "0 3px",
              }}
            >
              code.expired
            </span>
            <span style={{ color: "var(--ink-faint)" }}>: reject(410)</span>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              marginTop: 10,
            }}
          >
            {[
              ["you", "chose server-side validation", "var(--accent)"],
              ["ai", "decided to reject expired codes", GREEN],
              ["test", "rejects expired or unknown codes", "#5b8dc9"],
            ].map(([who, what, hue]) => (
              <div
                key={who}
                style={{ display: "flex", alignItems: "center", gap: 9 }}
              >
                <span
                  className="mono"
                  style={{
                    fontSize: 9,
                    fontWeight: 600,
                    textTransform: "uppercase",
                    color: hue,
                    width: 34,
                    flex: "none",
                  }}
                >
                  {who}
                </span>
                <span style={{ fontSize: 12, color: "var(--ink-90)" }}>
                  {what}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Page content ----------------------------------------------------------------

const DELIVERY = [
  {
    t: "Internal git",
    d: "A real, versioned repository from the first node — full history, diffs, and revert, managed for you.",
  },
  {
    t: "Your GitHub",
    d: "Push the project to your own GitHub org and keep building with your team on your terms.",
  },
  {
    t: "Download whole",
    d: "Export the entire project — code, tests, and artifacts — as a ZIP. It runs without Lothal.",
  },
];

const LANDING_CSS = `
  @media (max-width: 900px) {
    .lothal-surface .land-navlinks { display: none !important; }
    .lothal-surface .land-hero-split { grid-template-columns: 1fr !important; }
    .lothal-surface .land-hero-split > div:first-child { border-right: none !important; border-bottom: 1px solid var(--border) !important; }
    .lothal-surface .land-feature { grid-template-columns: 1fr !important; gap: 28px !important; }
    .lothal-surface .land-feature-visual { order: 2; }
    .lothal-surface .land-ribbon { grid-template-columns: 1fr 1fr !important; }
  }
`;

/** The landing content; assumes a surrounding LothalSurface for theme tokens. */
function LandingView() {
  const navigate = useNavigate();
  const goSignup = () => navigate("/signup");
  const goLogin = () => navigate("/login");

  useEffect(() => {
    document.title = "Lothal — software engineering, accelerated";
    return () => {
      document.title = "Lothal";
    };
  }, []);

  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => setScrolled(el.scrollTop > 8);
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (id: string) =>
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });

  const navLink = (label: string, id: string) => (
    <button
      type="button"
      onClick={() => scrollTo(id)}
      style={{
        border: "none",
        background: "transparent",
        padding: "6px 4px",
        fontFamily: "var(--sans)",
        fontSize: 13.5,
        color: "var(--ink-mute)",
        cursor: "pointer",
        transition: "color .15s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = "var(--ink)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = "var(--ink-mute)";
      }}
    >
      {label}
    </button>
  );

  const sectionPad = {
    maxWidth: 1120,
    margin: "0 auto",
    width: "100%",
    padding: "72px 32px",
    scrollMarginTop: 56,
    boxSizing: "border-box",
  } as const;

  return (
    <div ref={scrollRef} style={{ height: "100%", overflowY: "auto" }}>
      <style>{LANDING_CSS}</style>

      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          zIndex: 0,
          background:
            "radial-gradient(720px 420px at 78% -6%, var(--accent-soft), transparent 62%), radial-gradient(560px 380px at 6% 8%, var(--accent-soft), transparent 60%)",
        }}
      />

      <div style={{ position: "relative", zIndex: 1 }}>
        {/* ── Nav ── */}
        <header
          style={{
            position: "sticky",
            top: 0,
            zIndex: 50,
            borderBottom: `1px solid ${scrolled ? "var(--border)" : "transparent"}`,
            background: scrolled
              ? "color-mix(in srgb, var(--paper) 82%, transparent)"
              : "transparent",
            backdropFilter: scrolled ? "blur(12px)" : "none",
            WebkitBackdropFilter: scrolled ? "blur(12px)" : "none",
            transition: "background .25s ease, border-color .25s ease",
          }}
        >
          <div
            style={{
              maxWidth: 1120,
              margin: "0 auto",
              padding: "14px 32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 20,
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ color: "var(--accent)" }}>
                <LothalMark size={24} />
              </span>
              <span
                className="serif"
                style={{ fontSize: 22, letterSpacing: "-0.01em" }}
              >
                Lothal
              </span>
            </span>

            <nav
              className="land-navlinks"
              style={{ display: "flex", alignItems: "center", gap: 26 }}
              aria-label="Landing sections"
            >
              {navLink("How it works", SECTION_IDS.how)}
              {navLink("The gate", SECTION_IDS.gate)}
              {navLink("Change-aware", SECTION_IDS.tree)}
              {navLink("What you get", SECTION_IDS.deliver)}
            </nav>

            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Button variant="ghost" size="sm" onClick={goLogin}>
                Log in
              </Button>
              <Button variant="accent" size="sm" onClick={goSignup}>
                Sign up
              </Button>
            </div>
          </div>
        </header>

        {/* ── Hero ── */}
        <section
          style={{
            maxWidth: 1120,
            margin: "0 auto",
            width: "100%",
            padding: "72px 32px 40px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            gap: 22,
            boxSizing: "border-box",
          }}
        >
          <div
            className="fade-up"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 9,
              padding: "5px 12px 5px 9px",
              borderRadius: 999,
              border: "1px solid var(--border-strong)",
              background: "var(--surface)",
              fontSize: 12,
              color: "var(--ink-mute)",
            }}
          >
            <span
              className="pulse"
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--accent)",
              }}
            />
            Now in early access
          </div>

          <h1
            className="fade-up serif"
            style={{
              fontSize: "clamp(40px, 7vw, 76px)",
              lineHeight: 1.09,
              letterSpacing: "-0.02em",
              maxWidth: 900,
            }}
          >
            Build software the way you'd{" "}
            <span style={{ fontStyle: "italic", color: "var(--accent)" }}>
              explain
            </span>{" "}
            it.
            <br />
            Define “done” before you build it.
          </h1>

          <p
            className="fade-up"
            style={{
              fontSize: "clamp(15px, 1.6vw, 18px)",
              lineHeight: 1.6,
              color: "var(--ink-mute)",
              maxWidth: 640,
            }}
          >
            Describe what you want in plain language. Lothal clarifies it,
            designs an architecture you can see and shape, then builds it —
            proving every step against criteria you approved.
            Software-engineering discipline, accelerated by AI, and enforced at
            every step.
          </p>

          <div
            className="fade-up"
            style={{
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
              justifyContent: "center",
            }}
          >
            <Button variant="accent" size="lg" onClick={goSignup}>
              Sign up free
            </Button>
            <Button variant="outline" size="lg" onClick={goLogin}>
              Log in
            </Button>
          </div>

          <div className="fade-up" style={{ width: "100%", marginTop: 26 }}>
            <HeroScene />
          </div>
        </section>

        {/* ── Reframe: name the problem ── */}
        <section
          style={{
            background: "var(--paper-deep)",
            borderTop: "1px solid var(--border)",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <div
            style={{
              maxWidth: 900,
              margin: "0 auto",
              padding: "60px 32px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              gap: 18,
              alignItems: "center",
              boxSizing: "border-box",
            }}
          >
            <span className="label" style={{ color: "var(--accent)" }}>
              Not vibe-coding
            </span>
            <h2
              className="serif"
              style={{
                fontSize: "clamp(26px, 3.4vw, 38px)",
                lineHeight: 1.2,
                letterSpacing: "-0.015em",
                color: "var(--ink)",
                margin: 0,
              }}
            >
              Most AI builders remove the engineering.
              <br />
              Lothal keeps it — and removes the drudgery.
            </h2>
            <p
              style={{
                fontSize: 16,
                lineHeight: 1.7,
                color: "var(--ink-mute)",
                margin: 0,
                maxWidth: 680,
              }}
            >
              You prompt, it generates, and you find out what's wrong at the end
              — reading code no one specified, testing nothing you agreed on.
              Lothal runs the process a real engineer would: clarify the spec,
              design the architecture, freeze a definition of done, then prove
              each piece against it before anything depends on it. The same
              rigor a senior team brings — reached in a fraction of the time.
            </p>
            <p
              className="serif"
              style={{
                fontSize: "clamp(17px, 2vw, 21px)",
                fontStyle: "italic",
                color: "var(--ink)",
                margin: "4px 0 0",
                maxWidth: 660,
                lineHeight: 1.5,
              }}
            >
              The aim isn't to replace software development with AI. It's to
              accelerate it — with confidence and transparency.
            </p>
          </div>
        </section>

        {/* ── Phase ribbon (honest roadmap) ── */}
        <section id={SECTION_IDS.how} style={sectionPad}>
          <SectionHead
            eyebrow="How it works"
            title="From a sentence to a shipped build — one accountable step at a time."
            sub="A forward-only flow with a gate at every stage. Nothing advances until you approve it, and nothing is built until the plan is ratified."
          />
          <div
            className="land-ribbon"
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${PHASES.length}, 1fr)`,
              gap: 1,
              background: "var(--border)",
              border: "1px solid var(--border)",
              borderRadius: 14,
              overflow: "hidden",
              marginTop: 34,
            }}
          >
            {PHASES.map((p) => {
              const soon = isCodePhase(p.id);
              return (
                <div
                  key={p.id}
                  style={{
                    background: "var(--paper)",
                    padding: "18px 16px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    opacity: soon ? 0.66 : 1,
                  }}
                >
                  <span
                    className="mono"
                    style={{ fontSize: 11, color: "var(--accent)" }}
                  >
                    {p.short}
                  </span>
                  <span
                    className="serif"
                    style={{
                      fontSize: 18,
                      color: "var(--ink)",
                      lineHeight: 1.1,
                    }}
                  >
                    {p.label}
                  </span>
                  {soon && (
                    <span
                      className="mono"
                      style={{ fontSize: 9.5, color: "var(--ink-faint)" }}
                    >
                      coming next
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* ── Ladder ── */}
        <section
          style={{
            maxWidth: 1120,
            margin: "0 auto",
            width: "100%",
            padding: "8px 32px 24px",
            display: "flex",
            flexDirection: "column",
            gap: 88,
            boxSizing: "border-box",
          }}
        >
          {/* Clarify */}
          <FeatureRow
            eyebrow="01 · Clarify"
            title="No assumptions. It asks before it builds."
            body={
              <>
                The clarification loop keeps going — multiple-choice or free
                text, your call — until your intent and the spec are the same
                thing. What you approve is a{" "}
                <strong style={{ color: "var(--ink)" }}>
                  PRD you confirmed
                </strong>
                , not one the model guessed at.
              </>
            }
            visual={<PrdScene />}
          />

          {/* Architecture */}
          <FeatureRow
            flip
            eyebrow="02 · Design"
            title="Real architecture, before a line of code."
            body={
              <>
                From the spec, Lothal produces an{" "}
                <strong style={{ color: "var(--ink)" }}>
                  Architecture Decision Record
                </strong>{" "}
                — the chosen design, technology choices with rationale, and the
                alternatives it rejected and why — with a diagram set at four
                altitudes: system context, containers, data model, and runtime
                sequence. You refine it on a canvas; every edit is re-validated
                against the spec before it sticks.
              </>
            }
            aside="Then the build is risk-ordered: the parts most likely to break — the scariest endpoints first — are implemented and proven before anything depends on them."
            visual={<AdrScene />}
          />

          {/* The gate (flagship 1) */}
          <div id={SECTION_IDS.gate} style={{ scrollMarginTop: 56 }}>
            <FeatureRow
              eyebrow="The gate · enforced validation"
              title={
                <>
                  The AI doesn't get to say “done.”
                  <br />
                  It has to pass.
                </>
              }
              body={
                <>
                  Planning can be automated — creating a work item can't. Every
                  item is{" "}
                  <strong style={{ color: "var(--ink)" }}>required</strong> to
                  carry acceptance criteria before anything is built; Lothal
                  forces the model to write them, and you add your own on top.
                  Nothing is marked verified unless every criterion is covered
                  by a passing test. An uncovered criterion is rejected — and
                  unverified work can't advance, can't roll up, and can't reach
                  your codebase.
                </>
              }
              aside="Specify, then verify, at every level — criteria before build, tests before done, integration proven as it composes. A V-model discipline, enforced by the tool."
              visual={<GateScene />}
            />
          </div>

          {/* The contract tree (flagship 2 — centerpiece) */}
          <div id={SECTION_IDS.tree} style={{ scrollMarginTop: 56 }}>
            <FeatureRow
              flip
              eyebrow="Change-aware · the contract tree"
              title="Change one thing, and Lothal knows everything it touches."
              body={
                <>
                  The whole project is a live dependency tree of contracts,
                  built from the start. Change a node's contract and every
                  downstream node is automatically re-tested against it — in one
                  click. Whatever still holds, holds; whatever breaks is flagged
                  for you to update and re-ratify.{" "}
                  <strong style={{ color: "var(--ink)" }}>
                    No silent breakage three layers down. No surprises.
                  </strong>
                </>
              }
              visual={<ContractTreeScene />}
            />
          </div>

          {/* Git-per-node + traceability */}
          <FeatureRow
            eyebrow="Real & accountable"
            coming
            title="Every task ships like a developer finished it — and you can prove why."
            body={
              <>
                Git is managed for you: each completed node becomes its own
                commit, with a real history you can read, diff, and revert. And
                every line is accountable —{" "}
                <strong style={{ color: "var(--ink)" }}>
                  select any piece of the codebase and walk back
                </strong>{" "}
                through the inputs and decisions that produced it, yours and the
                AI's. Every line has a documented reason to exist.
              </>
            }
            visual={<GitTraceScene />}
          />
        </section>

        {/* ── Delivery ── */}
        <section
          id={SECTION_IDS.deliver}
          style={{
            background: "var(--paper-deep)",
            borderTop: "1px solid var(--border)",
            borderBottom: "1px solid var(--border)",
            scrollMarginTop: 56,
          }}
        >
          <div
            style={{
              maxWidth: 1120,
              margin: "0 auto",
              width: "100%",
              padding: "64px 32px",
              boxSizing: "border-box",
            }}
          >
            <SectionHead
              eyebrow="What you get"
              title="The code is yours, and it's real."
              sub="A versioned git repo — every node a commit — that you can push to your own GitHub or export whole. No lock-in. No black box."
            />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                gap: 14,
                marginTop: 36,
              }}
            >
              {DELIVERY.map((w) => (
                <div
                  key={w.t}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 14,
                    background: "var(--surface)",
                    padding: "22px 20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <h3
                    className="serif"
                    style={{ fontSize: 22, color: "var(--ink)" }}
                  >
                    {w.t}
                  </h3>
                  <p
                    style={{
                      fontSize: 13.5,
                      lineHeight: 1.6,
                      color: "var(--ink-mute)",
                      margin: 0,
                    }}
                  >
                    {w.d}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Closing CTA ── */}
        <section
          style={{
            maxWidth: 1120,
            margin: "0 auto",
            width: "100%",
            padding: "8px 32px 80px",
            boxSizing: "border-box",
          }}
        >
          <div
            style={{
              position: "relative",
              overflow: "hidden",
              borderRadius: 20,
              border: "1px solid var(--border-strong)",
              background: "var(--surface)",
              padding: "56px 40px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 18,
            }}
          >
            <div
              aria-hidden
              style={{
                position: "absolute",
                inset: 0,
                pointerEvents: "none",
                background:
                  "radial-gradient(600px 300px at 50% -20%, var(--accent-soft), transparent 70%)",
              }}
            />
            <h2
              className="serif"
              style={{
                fontSize: "clamp(32px, 5vw, 52px)",
                lineHeight: 1.12,
                letterSpacing: "-0.02em",
                maxWidth: 640,
                position: "relative",
              }}
            >
              Your next project starts with a sentence.
            </h2>
            <p
              style={{
                fontSize: 16,
                color: "var(--ink-mute)",
                maxWidth: 520,
                position: "relative",
                margin: 0,
                lineHeight: 1.6,
              }}
            >
              No setup, no boilerplate, no guessing what the AI understood — and
              nothing in your codebase you didn't verify. Just describe it.
            </p>
            <div
              style={{
                display: "flex",
                gap: 10,
                position: "relative",
                flexWrap: "wrap",
                justifyContent: "center",
              }}
            >
              <Button variant="accent" size="lg" onClick={goSignup}>
                Sign up free
              </Button>
              <Button variant="outline" size="lg" onClick={goLogin}>
                Log in
              </Button>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer style={{ borderTop: "1px solid var(--border)" }}>
          <div
            style={{
              maxWidth: 1120,
              margin: "0 auto",
              padding: "28px 32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              flexWrap: "wrap",
              boxSizing: "border-box",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ color: "var(--accent)" }}>
                <LothalMark size={20} />
              </span>
              <span className="serif" style={{ fontSize: 18 }}>
                Lothal
              </span>
              <span
                style={{
                  fontSize: 12.5,
                  color: "var(--ink-soft)",
                  marginLeft: 6,
                }}
              >
                software engineering, accelerated
              </span>
            </div>
            <div
              style={{
                display: "flex",
                gap: 22,
                fontSize: 12.5,
                color: "var(--ink-soft)",
              }}
            >
              <span>© 2026 Lothal</span>
              <span className="mono">v{LOTHAL_VERSION}</span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

/** The Clarify row's visual: the confirmed PRD — the output of the clarification
 *  loop — so the rung shows what you approve, not a repeat of the hero chat. */
function PrdScene() {
  const reqs = [
    "One page to create a link and view its stats",
    "302 redirect on visit, with a per-link click count",
    "REST API for create / resolve / stats",
    "No auth — open and anonymous by design",
  ];
  return (
    <div
      style={{
        borderRadius: 14,
        border: "1px solid var(--border-strong)",
        background: "var(--paper)",
        overflow: "hidden",
        boxShadow: "0 30px 70px -40px rgba(0,0,0,.5)",
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <span className="label">PRD · larder</span>
        <span
          className="mono"
          style={{ fontSize: 10, color: "var(--ink-faint)" }}
        >
          confirmed with you
        </span>
        {chip("approved", GREEN)}
      </div>
      <div
        style={{
          padding: 18,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <span className="serif" style={{ fontSize: 17, color: "var(--ink)" }}>
          A minimal URL shortener
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          {reqs.map((r) => (
            <div
              key={r}
              style={{ display: "flex", gap: 9, alignItems: "center" }}
            >
              <span
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: 4,
                  flex: "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 10,
                  color: "#fff",
                  background: GREEN,
                }}
              >
                ✓
              </span>
              <span style={{ fontSize: 13, color: "var(--ink-90)" }}>{r}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** The Architecture row's visual: an ADR — the chosen decision plus the
 *  alternatives it rejected and why, with the four diagram altitudes. */
function AdrScene() {
  return (
    <div
      style={{
        borderRadius: 14,
        border: "1px solid var(--border-strong)",
        background: "var(--paper)",
        overflow: "hidden",
        boxShadow: "0 30px 70px -40px rgba(0,0,0,.5)",
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <span className="label">ADR 001</span>
        <span
          className="mono"
          style={{ fontSize: 10, color: "var(--ink-faint)" }}
        >
          architecture decision
        </span>
      </div>
      <div
        style={{
          padding: 18,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div>
          <div className="label" style={{ marginBottom: 6 }}>
            Decision
          </div>
          <span
            style={{ fontSize: 13.5, color: "var(--ink-90)", lineHeight: 1.5 }}
          >
            A single service serving the API and static UI — atomic click counts
            in Postgres, base62 short codes.
          </span>
        </div>
        <div>
          <div className="label" style={{ marginBottom: 6 }}>
            Rejected
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {[
              ["Redis counter", "adds a moving part before it's needed"],
              ["Sequential IDs", "leak volume and are enumerable"],
            ].map(([opt, why]) => (
              <div
                key={opt}
                style={{ display: "flex", gap: 8, alignItems: "baseline" }}
              >
                <span
                  className="mono"
                  style={{ fontSize: 10, color: "#c05b52", flex: "none" }}
                >
                  ✕ {opt}
                </span>
                <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
                  {why}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div
          style={{
            display: "flex",
            gap: 6,
            flexWrap: "wrap",
            borderTop: "1px solid var(--border)",
            paddingTop: 12,
          }}
        >
          {["context", "containers", "data model", "sequence"].map((d) => (
            <span
              key={d}
              className="mono"
              style={{
                fontSize: 10,
                color: "var(--ink-soft)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "3px 8px",
              }}
            >
              {d}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/** Public landing page at "/" — marketing surface on the Lothal theme. */
export default function Landing() {
  return (
    <LothalSurface>
      <LandingView />
    </LothalSurface>
  );
}
