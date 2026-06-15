// Lothal landing page (Epic 0.5) — the public front door at "/". A faithful
// port of the landing design (Lothal/src/landing.jsx in the design bundle):
// sticky blur nav, centered hero with an early-access pill and a live product
// preview of the sample bakery project ("larder" — clarification chat beside
// a real diagram canvas), a principles grid, the five steps, a canvas
// showcase band, delivery cards, a glowing closing CTA, and the footer.
// Anonymous visitors funnel into /login?redirect=/lothal; authenticated
// users go straight to the dashboard.

import { type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type {
  DiagramEdge,
  DiagramNode,
} from "@/controllers/API/queries/lothal";
import useAuthStore from "@/stores/authStore";
import {
  Button,
  DiagramCanvas,
  LOTHAL_VERSION,
  LothalMark,
  type LothalPhaseId,
  PHASES,
} from "../components";
import { LothalSurface } from "../theme/LothalSurface";

// Step copy from the design, keyed by the shared phase ids so a phase added
// or renamed in phases.ts fails loudly here instead of drifting.
const STEP_COPY: Record<LothalPhaseId, string> = {
  CLARIFICATION:
    "Describe what you want in plain words. Lothal responds with focused questions — multiple choice or free text — until there are no assumptions left.",
  DIAGRAM_GENERATION:
    "Once it understands, Lothal drafts a sequence diagram of your solution: the actors, the calls between them, and the order things happen.",
  DIAGRAM_REFINEMENT:
    "Drag nodes and rewire edges on the canvas, or just say what's wrong. Each change is checked against the agreed spec before it sticks.",
  CODE_GENERATION:
    "With the diagram locked, Lothal writes the full codebase, committing to an internal Git repository as it goes.",
  DONE: "Pull the repo, push to your own GitHub, or download a ZIP. The code traces back to a design you verified, step by step.",
};

const SECTION_IDS = {
  how: "lothal-how",
  canvas: "lothal-canvas",
  deliver: "lothal-deliver",
} as const;

// --- The sample bakery project ("larder") --------------------------------------
// The same mini system the design mocks up, rendered on the real canvas: a
// customer submits an order, the order service reserves stock, inventory
// reports back, and the kitchen board pings the customer.

const LARDER_NODES: DiagramNode[] = [
  {
    id: "customer",
    type: "actorNode",
    position: { x: 20, y: 50 },
    data: { label: "Customer" },
  },
  {
    id: "order",
    type: "systemNode",
    position: { x: 330, y: 50 },
    data: { label: "Order Service" },
  },
  {
    id: "inventory",
    type: "systemNode",
    position: { x: 330, y: 230 },
    data: { label: "Inventory" },
  },
  {
    id: "kitchen",
    type: "systemNode",
    position: { x: 20, y: 230 },
    data: { label: "Kitchen Board", kind: "ui" },
  },
];

const LARDER_EDGES: DiagramEdge[] = [
  {
    id: "e1",
    source: "customer",
    target: "order",
    label: "submit order",
    data: { order: 1, kind: "sync" },
  },
  {
    id: "e2",
    source: "order",
    target: "inventory",
    label: "reserve stock",
    data: { order: 2, kind: "sync" },
  },
  {
    id: "e3",
    source: "inventory",
    target: "kitchen",
    label: "stock status",
    data: { order: 3, kind: "return" },
  },
  {
    id: "e4",
    source: "kitchen",
    target: "customer",
    label: "ready for pickup",
    data: { order: 4, kind: "async" },
  },
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
        {/* user */}
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
        {/* assistant question with choice chips */}
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
        {/* assistant streaming line */}
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
            That's enough to draft a sequence
            <span className="caret" />
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
          <span>Type your answer…</span>
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
      {/* Window chrome */}
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

      {/* Split: chat + canvas */}
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
            <span className="label">Canvas</span>
            <span
              className="mono"
              style={{ fontSize: 10, color: "var(--ink-faint)" }}
            >
              {LARDER_NODES.length} nodes · {LARDER_EDGES.length} edges
            </span>
          </div>
          <DiagramCanvas
            id="landing-hero"
            nodes={LARDER_NODES}
            edges={LARDER_EDGES}
            chrome={false}
            zoomOnScroll={false}
          />
        </div>
      </div>
    </div>
  );
}

// --- Section head helper ---------------------------------------------------------

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
        maxWidth: align === "center" ? 640 : "none",
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

// --- Page --------------------------------------------------------------------------

const PRINCIPLES = [
  {
    k: "No assumptions",
    v: "Lothal asks before it builds. The clarification loop keeps going until your intent and the spec are the same thing.",
  },
  {
    k: "Diagram before code",
    v: "You see and shape the architecture as a sequence diagram first. Nothing is generated until you approve it.",
  },
  {
    k: "You stay in control",
    v: "Edit on the canvas or in plain language. Every change is validated against the spec, then re-rendered.",
  },
];

const CANVAS_FEATS = [
  "Drag nodes, rewire edges, edit labels inline",
  "Pan, zoom, fit-to-view, and a live mini-map",
  "Sync, async, and return calls, drawn distinctly",
  "Every edit re-validated against your spec",
];

const DELIVERY_WAYS = [
  {
    t: "Internal Git",
    d: "Every diagram revision and code generation is a versioned commit. Nothing is lost between sessions.",
  },
  {
    t: "Your GitHub",
    d: "Push the finished repository straight to a GitHub repo you own, whenever you're ready.",
  },
  {
    t: "Download ZIP",
    d: "Prefer to take it offline? Export the whole codebase as a ZIP in one click.",
  },
];

// Responsive tweaks for the landing, scoped under the lothal surface.
const LANDING_CSS = `
  @media (max-width: 860px) {
    .lothal-surface .land-navlinks { display: none !important; }
    .lothal-surface .land-hero-split { grid-template-columns: 1fr !important; }
    .lothal-surface .land-hero-split > div:first-child { border-right: none !important; border-bottom: 1px solid var(--border) !important; }
    .lothal-surface .land-showcase { grid-template-columns: 1fr !important; }
    .lothal-surface .land-step { grid-template-columns: auto 1fr !important; gap: 16px !important; }
    .lothal-surface .land-step h3 { grid-column: 2; }
    .lothal-surface .land-step p { grid-column: 2; }
  }
`;

/** The landing content; assumes a surrounding LothalSurface for theme tokens. */
function LandingView() {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const autoLogin = useAuthStore((s) => s.autoLogin);
  // autoLogin === true means the backend signs everyone in — treat as authed,
  // mirroring ProtectedLoginRoute.
  const authed = isAuthenticated || autoLogin === true;

  // The CTA funnels into the Lothal dashboard; anonymous visitors pass the
  // destination to the login page via the redirect param it already honors.
  const enter = () => navigate(authed ? "/lothal" : "/login?redirect=/lothal");
  const startLabel = authed ? "Open dashboard" : "Start building";
  const startLabelLg = authed ? "Open dashboard" : "Start building free";

  // The marketing title, restored to the app default on the way out.
  useEffect(() => {
    document.title = "Lothal — build software by describing it";
    return () => {
      document.title = "Lothal";
    };
  }, []);

  // The nav gains a blur backdrop once the page scrolls.
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

  return (
    <div ref={scrollRef} style={{ height: "100%", overflowY: "auto" }}>
      <style>{LANDING_CSS}</style>

      {/* Ambient aubergine glow behind the hero. */}
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
              {navLink("The canvas", SECTION_IDS.canvas)}
              {navLink("Delivery", SECTION_IDS.deliver)}
            </nav>

            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {!authed && (
                <Button variant="ghost" size="sm" onClick={enter}>
                  Sign in
                </Button>
              )}
              <Button variant="accent" size="sm" onClick={enter}>
                {startLabel}
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
            Built on Langflow · now in early access
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
            Build software the way
            <br />
            you'd{" "}
            <span style={{ fontStyle: "italic", color: "var(--accent)" }}>
              explain
            </span>{" "}
            it to someone.
          </h1>

          <p
            className="fade-up"
            style={{
              fontSize: "clamp(15px, 1.6vw, 18px)",
              lineHeight: 1.6,
              color: "var(--ink-mute)",
              maxWidth: 600,
            }}
          >
            Describe what you want in plain language. Lothal asks the right
            questions, draws a diagram you can shape by hand, and turns the
            approved design into a working, version-controlled codebase.
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
            <Button variant="accent" size="lg" onClick={enter}>
              {startLabelLg}
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => scrollTo(SECTION_IDS.how)}
            >
              See how it works
            </Button>
          </div>

          <div className="fade-up" style={{ width: "100%", marginTop: 26 }}>
            <HeroScene />
          </div>
        </section>

        {/* ── Principles strip ── */}
        <section
          style={{
            maxWidth: 1120,
            margin: "0 auto",
            width: "100%",
            padding: "44px 32px",
            boxSizing: "border-box",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: 1,
              background: "var(--border)",
              border: "1px solid var(--border)",
              borderRadius: 14,
              overflow: "hidden",
            }}
          >
            {PRINCIPLES.map((it) => (
              <div
                key={it.k}
                style={{
                  background: "var(--paper)",
                  padding: "24px 22px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <h3
                  className="serif"
                  style={{ fontSize: 21, color: "var(--ink)" }}
                >
                  {it.k}
                </h3>
                <p
                  style={{
                    fontSize: 13.5,
                    lineHeight: 1.6,
                    color: "var(--ink-mute)",
                    margin: 0,
                  }}
                >
                  {it.v}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── How it works ── */}
        <section
          id={SECTION_IDS.how}
          style={{
            maxWidth: 1120,
            margin: "0 auto",
            width: "100%",
            padding: "60px 32px",
            scrollMarginTop: 56,
            boxSizing: "border-box",
          }}
        >
          <SectionHead
            eyebrow="How it works"
            title="Five steps from a sentence to a codebase."
            sub="A forward-only flow. You can't skip ahead to code before the diagram is approved — that's the point."
          />
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 0,
              marginTop: 36,
            }}
          >
            {PHASES.map((p) => (
              <div
                key={p.id}
                className="land-step"
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 200px 1fr",
                  gap: 28,
                  alignItems: "start",
                  padding: "26px 0",
                  borderTop: "1px solid var(--border)",
                }}
              >
                <span
                  className="mono"
                  style={{
                    fontSize: 13,
                    color: "var(--accent)",
                    paddingTop: 4,
                  }}
                >
                  {p.short}
                </span>
                <h3
                  className="serif"
                  style={{ fontSize: 30, color: "var(--ink)", lineHeight: 1 }}
                >
                  {p.label}
                </h3>
                <p
                  style={{
                    fontSize: 15,
                    lineHeight: 1.6,
                    color: "var(--ink-mute)",
                    margin: 0,
                    maxWidth: 560,
                  }}
                >
                  {STEP_COPY[p.id]}
                </p>
              </div>
            ))}
            <div style={{ borderTop: "1px solid var(--border)" }} />
          </div>
        </section>

        {/* ── Canvas showcase ── */}
        <section
          id={SECTION_IDS.canvas}
          style={{
            background: "var(--paper-deep)",
            borderTop: "1px solid var(--border)",
            borderBottom: "1px solid var(--border)",
            scrollMarginTop: 56,
          }}
        >
          <div
            className="land-showcase"
            style={{
              maxWidth: 1120,
              margin: "0 auto",
              width: "100%",
              padding: "64px 32px",
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 48,
              alignItems: "center",
              boxSizing: "border-box",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <SectionHead
                align="left"
                eyebrow="The canvas"
                title="A real diagram, not a black box."
                sub="The same node-and-edge canvas Langflow uses to wire up agents. Your architecture is something you can actually touch."
              />
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                  marginTop: 4,
                }}
              >
                {CANVAS_FEATS.map((f) => (
                  <div
                    key={f}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 10,
                    }}
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
                      {f}
                    </span>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 10 }}>
                <Button variant="accent" onClick={enter}>
                  Open the canvas
                </Button>
              </div>
            </div>

            <div
              style={{
                borderRadius: 14,
                border: "1px solid var(--border-strong)",
                background: "var(--paper)",
                overflow: "hidden",
                boxShadow: "0 30px 70px -40px rgba(0,0,0,.5)",
                position: "relative",
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
                <span className="label">Sequence diagram</span>
                <span
                  className="mono"
                  style={{ fontSize: 10, color: "var(--ink-faint)" }}
                >
                  v2 · refining
                </span>
                <span style={{ flex: 1 }} />
                <span
                  className="mono"
                  style={{ fontSize: 10.5, color: "var(--ink-soft)" }}
                >
                  120%
                </span>
              </div>
              <div style={{ position: "relative", height: 300 }}>
                <DiagramCanvas
                  id="landing-showcase"
                  nodes={LARDER_NODES}
                  edges={LARDER_EDGES}
                  zoomOnScroll={false}
                />
              </div>
            </div>
          </div>
        </section>

        {/* ── Delivery ── */}
        <section
          id={SECTION_IDS.deliver}
          style={{
            maxWidth: 1120,
            margin: "0 auto",
            width: "100%",
            padding: "64px 32px",
            scrollMarginTop: 56,
            boxSizing: "border-box",
          }}
        >
          <SectionHead
            eyebrow="Delivery"
            title="The code is yours, traceable to a design you approved."
            sub="Projects are persistent and resumable. Close the tab and come back — the conversation, the diagram, and the phase you were in are all restored."
          />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: 14,
              marginTop: 36,
            }}
          >
            {DELIVERY_WAYS.map((w) => (
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
        </section>

        {/* ── Closing CTA ── */}
        <section
          style={{
            maxWidth: 1120,
            margin: "0 auto",
            width: "100%",
            padding: "20px 32px 80px",
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
                maxWidth: 480,
                position: "relative",
                margin: 0,
              }}
            >
              No setup, no boilerplate, no guessing what the AI understood. Just
              describe it.
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
              <Button variant="accent" size="lg" onClick={enter}>
                {startLabelLg}
              </Button>
              {!authed && (
                <Button variant="outline" size="lg" onClick={enter}>
                  Sign in
                </Button>
              )}
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
                build software by describing it
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
              <span className="mono">built on langflow</span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

/** Public landing page at "/" — marketing surface on the dockyard theme. */
export default function Landing() {
  return (
    <LothalSurface>
      <LandingView />
    </LothalSurface>
  );
}
