// Lothal landing page (Epic 0.5) — the public front door at "/". The marketing
// surface for the verification-driven build pipeline: a sticky blur nav, a
// centered hero with an early-access pill and a live product preview of the
// sample bakery project ("larder" — clarification chat beside a diagram), a
// principles grid, the six stages (Clarify → Design → Prototype → Plan →
// Generate → Deliver), a verification-driven-planning band (the differentiator),
// the artifacts you accumulate, a glowing closing CTA, and the footer. Stages 5
// and 6 (Generate, Deliver) are not built yet, so they're tagged "Coming next".
// The page's only actions are Log in and Sign up — it never opens the projects
// app directly; /lothal lives behind auth (ProtectedRoute).

import { type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  isCodePhase,
  LOTHAL_VERSION,
  LothalMark,
  type LothalPhaseId,
  PHASES,
  SampleDiagram,
  type SampleMessage,
  type SampleParticipant,
} from "../components";
import { LothalSurface } from "../theme/LothalSurface";

// Step copy from the design, keyed by the shared phase ids so a phase added
// or renamed in phases.ts fails loudly here instead of drifting. The Record
// requires all six keys — Generate and Deliver aren't built yet (they're tagged
// "Coming next" in the UI), so their copy is written in a forward register.
const STEP_COPY: Record<LothalPhaseId, string> = {
  CLARIFICATION:
    "Describe what you want in plain words; Lothal answers with focused questions — multiple choice or free text — until no assumptions are left, then captures it as a PRD.",
  ARCHITECTURE:
    "Lothal turns the spec into an Architecture Decision Record plus context, container, data-model, and sequence diagrams — refined by conversation and approved by you.",
  PROTOTYPE:
    "From the approved design, Lothal drives Open Design to produce an interactive UI/UX prototype you can preview, edit, and comment on without leaving the page.",
  PLAN: "Lothal breaks the work into a tree — app, component, epic, story — and gives each item an assume-guarantee contract, acceptance criteria, and frozen tests before a line is written.",
  CODE_GENERATION:
    "Each ratified item is implemented against the very tests and contract it was frozen with — a definition of done the build can't move.",
  DONE: "Leave with every artifact — PRD, diagrams, prototype, and code — each one traceable back to the plan you ratified.",
};

// A short serif lead shown under each step's label.
const STEP_LEAD: Record<LothalPhaseId, string> = {
  CLARIFICATION: "Questions until the spec is solid",
  ARCHITECTURE: "An ADR and four diagrams",
  PROTOTYPE: "See it before you build it",
  PLAN: "Every item carries a contract",
  CODE_GENERATION: "Built against a frozen spec",
  DONE: "Take the whole project with you",
};

const SECTION_IDS = {
  how: "lothal-how",
  plan: "lothal-plan",
  deliver: "lothal-deliver",
} as const;

// --- The sample bakery project ("larder") --------------------------------------
// The same mini system the design mocks up, drawn as a sequence diagram (the
// product's real output, Epic D): a customer submits an order, the order service
// reserves stock, inventory reports back, and the kitchen board pings the
// customer. Decorative — <SampleDiagram> is a static illustration, not the live
// <D2Canvas>.

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

// --- Plan node preview (the verification band's right visual) --------------------

/** A static mock of a PLAN node's detail: kind, state machine, frozen contract,
 *  and frozen tests — the verification artifact the differentiator describes. */
function PlanNodeScene() {
  const states = [
    "draft",
    "ratified",
    "in-progress",
    "in-verification",
    "verified",
  ];
  const current = "ratified";
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
  const cardLabel = (label: string) => (
    <span
      style={{
        display: "flex",
        alignItems: "center",
        gap: 7,
        marginBottom: 9,
      }}
    >
      <span className="label" style={{ color: "var(--ink-mute)" }}>
        {label}
      </span>
      <span
        className="mono"
        style={{
          fontSize: 9,
          color: "var(--ink-soft)",
          border: "1px solid var(--border)",
          borderRadius: 5,
          padding: "1px 6px",
        }}
      >
        frozen ⟡
      </span>
    </span>
  );
  const cardStyle = {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 11,
    padding: "13px 15px",
  } as const;
  const bullet = (mark: string, hue: string, text: string) => (
    <div
      style={{
        display: "flex",
        gap: 8,
        fontSize: 12.5,
        color: "var(--ink-90)",
        lineHeight: 1.45,
      }}
    >
      <span style={{ color: hue, flex: "none", fontWeight: 700 }}>{mark}</span>
      <span>{text}</span>
    </div>
  );

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
        <span className="label">Plan</span>
        <span
          className="mono"
          style={{ fontSize: 10, color: "var(--ink-faint)" }}
        >
          node detail
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
          {chip("story", "#4e9a6a")}
          <span className="serif" style={{ fontSize: 18, color: "var(--ink)" }}>
            Apply a discount code at checkout
          </span>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {states.map((s) => {
            const on = s === current;
            return (
              <span
                key={s}
                className="mono"
                style={{
                  fontSize: 10,
                  padding: "3px 8px",
                  borderRadius: 999,
                  color: on ? "var(--accent-fg)" : "var(--ink-soft)",
                  background: on ? "var(--accent)" : "var(--surface)",
                  border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`,
                }}
              >
                {s}
              </span>
            );
          })}
        </div>

        <div style={cardStyle}>
          {cardLabel("Contract")}
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            <div>
              <div className="label" style={{ marginBottom: 4 }}>
                Assumes
              </div>
              {bullet(
                "→",
                "var(--ink-soft)",
                "a valid cart and a signed-in shopper",
              )}
            </div>
            <div>
              <div className="label" style={{ marginBottom: 4 }}>
                Guarantees
              </div>
              {bullet("✓", "#4e9a6a", "one discount applied, or a typed error")}
            </div>
          </div>
        </div>

        <div style={cardStyle}>
          {cardLabel("Tests")}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span
                className="mono"
                style={{
                  fontSize: 9.5,
                  color: "#5b8dc9",
                  flex: "none",
                  width: 64,
                }}
              >
                unit
              </span>
              <span style={{ flex: 1, fontSize: 12, color: "var(--ink-90)" }}>
                rejects expired or unknown codes
              </span>
              {chip("pass", "#4e9a6a")}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span
                className="mono"
                style={{
                  fontSize: 9.5,
                  color: "#c074b0",
                  flex: "none",
                  width: 64,
                }}
              >
                integration
              </span>
              <span style={{ flex: 1, fontSize: 12, color: "var(--ink-90)" }}>
                recomputes the order total
              </span>
              {chip("pending", "var(--ink-soft)")}
            </div>
          </div>
        </div>

        <span
          className="mono"
          style={{ fontSize: 10.5, color: "var(--ink-soft)" }}
        >
          read-only to the implementer
        </span>
      </div>
    </div>
  );
}

// --- Page --------------------------------------------------------------------------

const PRINCIPLES = [
  {
    k: "Nothing built on a guess",
    v: "The clarification loop runs until your intent and the spec are the same thing. Lothal asks before it builds.",
  },
  {
    k: "'Done' is defined first",
    v: "Every item gets a contract, acceptance criteria, and frozen tests before implementation — a definition of done that can't quietly drift.",
  },
  {
    k: "You hold every gate",
    v: "Designs, prototypes, and plans only move forward when you approve them. The flow is forward-only by design.",
  },
];

const PLAN_FEATS = [
  "Frozen on ratification — contracts, criteria, and tests can't silently drift once work begins.",
  "A roll-up gate — a parent only turns verified when every child is verified and its integration tests pass.",
  "Surgical invalidation — change a contract and only the items downstream of it need re-checking.",
];

const ARTIFACTS = [
  {
    t: "A clear spec",
    d: "A PRD synthesized from the clarification conversation — the confirmed definition of what to build.",
  },
  {
    t: "An architecture you approved",
    d: "An ADR plus context, container, data-model, and sequence diagrams, refined until they're right.",
  },
  {
    t: "An interactive prototype",
    d: "A real UI/UX prototype you shaped and signed off — not a static mockup.",
  },
  {
    t: "A verification-ready plan",
    d: "A tree of items, each with a frozen contract, acceptance criteria, and tests — the blueprint the build runs against.",
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
    .lothal-surface .land-step-label { grid-column: 2; }
    .lothal-surface .land-step p { grid-column: 2; }
  }
`;

/** The landing content; assumes a surrounding LothalSurface for theme tokens. */
function LandingView() {
  const navigate = useNavigate();

  // The landing's only actions: create an account or sign in. The Lothal login
  // page defaults its own post-login redirect to /lothal, so these go plain.
  const goSignup = () => navigate("/signup");
  const goLogin = () => navigate("/login");

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
              {navLink("Verification", SECTION_IDS.plan)}
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
              maxWidth: 600,
            }}
          >
            Describe what you want in plain language. Lothal asks the right
            questions, designs the architecture, and shapes an interactive
            prototype with you — then turns it into a plan where every piece of
            work carries a contract and frozen tests, before a line of code is
            written.
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
            title="Six stages, from a sentence to a build-ready plan."
            sub="A forward-only flow with an approval gate at every stage. Nothing advances until you sign off — and nothing is built until the plan is ratified."
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
                <div
                  className="land-step-label"
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                  }}
                >
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 9,
                      flexWrap: "wrap",
                    }}
                  >
                    <h3
                      className="serif"
                      style={{
                        fontSize: 30,
                        color: "var(--ink)",
                        lineHeight: 1,
                        margin: 0,
                      }}
                    >
                      {p.label}
                    </h3>
                    {isCodePhase(p.id) && (
                      <span
                        className="mono"
                        style={{
                          fontSize: 10.5,
                          color: "var(--ink-faint)",
                          border: "1px solid var(--border)",
                          borderRadius: 999,
                          padding: "2px 8px",
                          whiteSpace: "nowrap",
                        }}
                      >
                        Coming next
                      </span>
                    )}
                  </span>
                  <span
                    className="serif"
                    style={{
                      fontSize: 14.5,
                      fontStyle: "italic",
                      color: "var(--ink-soft)",
                      lineHeight: 1.3,
                    }}
                  >
                    {STEP_LEAD[p.id]}
                  </span>
                </div>
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

        {/* ── Verification-driven planning (the differentiator) ── */}
        <section
          id={SECTION_IDS.plan}
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
                eyebrow="Verification-driven planning"
                title="Proven before it composes."
              />
              <p
                style={{
                  fontSize: 15,
                  lineHeight: 1.7,
                  color: "var(--ink-mute)",
                  margin: 0,
                  maxWidth: 540,
                }}
              >
                Most AI builders sprint from prompt to output and leave you to
                find what's wrong. Lothal works the other way around. Before
                anything is built, every item in the plan — app, component,
                epic, story — gets an assume-guarantee contract: what it needs
                coming in, what it promises going out. Ratify it, and that
                contract, its acceptance criteria, and its tests freeze into a
                definition of done the implementation can't move. A roll-up gate
                then holds every parent open until its children are verified —
                so correctness composes upward through contracts you approved.
              </p>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                  marginTop: 4,
                }}
              >
                {PLAN_FEATS.map((f) => (
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
            </div>

            <PlanNodeScene />
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
            eyebrow="What you get"
            title="Real artifacts at every step, not just a final answer."
            sub="Every project is persistent and resumable — close the tab and come back to the same conversation, design, prototype, and plan, exactly where you left them."
          />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: 14,
              marginTop: 36,
            }}
          >
            {ARTIFACTS.map((w) => (
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
              No setup, no boilerplate, no guessing what the AI understood.
              Describe it — and approve every step before it's built.
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

/** Public landing page at "/" — marketing surface on the Lothal theme. */
export default function Landing() {
  return (
    <LothalSurface>
      <LandingView />
    </LothalSurface>
  );
}
