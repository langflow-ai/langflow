// Lothal landing page (Story 0.5) — the public front door at "/". A marketing
// surface on the dockyard design system: an editorial hero over the harbor
// watermark, the five-phase journey (driven by the shared PHASES metadata),
// the three artifacts, and a footer. Anonymous visitors get a sign-in CTA
// that funnels into the Lothal dashboard; authenticated users go straight in.

import type { CSSProperties, ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import useAuthStore from "@/stores/authStore";
import {
  Button,
  HarborWatermark,
  LothalMark,
  type LothalPhaseId,
  PHASES,
  TopBar,
} from "../components";
import { LothalSurface, useLothalTheme } from "../theme/LothalSurface";

// Landing copy for each phase, keyed by the shared phase ids so a phase
// added or renamed in phases.ts fails loudly here instead of drifting.
const PHASE_COPY: Record<LothalPhaseId, string> = {
  CLARIFICATION:
    "Patient questions until the idea has edges. Nothing gets assumed on your behalf.",
  DIAGRAM_GENERATION:
    "Your answers become a sequence diagram — every actor, system, and message in one picture.",
  DIAGRAM_REFINEMENT:
    "Argue with the diagram, not the code. Moving a line here beats a refactor later.",
  CODE_GENERATION:
    "The diagram you signed off on becomes a working codebase, file by file.",
  DONE: "A build you can run, read, and take with you. The diagram ships alongside it.",
};

const JOURNEY_SECTION_ID = "lothal-journey";

function SectionHeading({
  kicker,
  title,
  sub,
}: {
  kicker: string;
  title: ReactNode;
  sub?: string;
}) {
  return (
    <div style={{ maxWidth: 560 }}>
      <div className="label" style={{ color: "var(--accent)" }}>
        {kicker}
      </div>
      <h2
        className="serif"
        style={{ marginTop: 10, fontSize: 32, lineHeight: 1.15 }}
      >
        {title}
      </h2>
      {sub && (
        <p
          style={{
            marginTop: 10,
            fontSize: 14.5,
            lineHeight: 1.6,
            color: "var(--ink-mute)",
          }}
        >
          {sub}
        </p>
      )}
    </div>
  );
}

function Card({
  children,
  style,
}: {
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        padding: 20,
        borderRadius: "var(--radius-lg)",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function PhaseCard({
  short,
  label,
  action,
  copy,
}: {
  short: string;
  label: string;
  action: boolean;
  copy: string;
}) {
  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 10,
        }}
      >
        <span
          className="mono"
          style={{ fontSize: 12, color: "var(--ink-soft)" }}
        >
          {short}
        </span>
        <span
          className="mono"
          style={{
            fontSize: 10.5,
            color: action ? "var(--accent)" : "var(--ink-soft)",
          }}
        >
          {action ? "you steer" : "lothal builds"}
        </span>
      </div>
      <span className="serif" style={{ fontSize: 22, lineHeight: 1.1 }}>
        {label}
      </span>
      <p style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--ink-mute)" }}>
        {copy}
      </p>
    </Card>
  );
}

function ArtifactCard({ title, copy }: { title: string; copy: string }) {
  return (
    <Card>
      <span
        className="serif"
        style={{ fontSize: 21, lineHeight: 1.15, fontStyle: "italic" }}
      >
        {title}
      </span>
      <p style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--ink-mute)" }}>
        {copy}
      </p>
    </Card>
  );
}

function LandingView() {
  const navigate = useNavigate();
  const { theme } = useLothalTheme();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const autoLogin = useAuthStore((s) => s.autoLogin);
  // autoLogin === true means the backend signs everyone in — treat as authed,
  // mirroring ProtectedLoginRoute.
  const authed = isAuthenticated || autoLogin === true;

  // The CTA funnels into the Lothal dashboard; anonymous visitors pass the
  // destination to the login page via the redirect param it already honors.
  const enter = () => navigate(authed ? "/lothal" : "/login?redirect=/lothal");

  const showJourney = () =>
    document
      .getElementById(JOURNEY_SECTION_ID)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <TopBar
        left={
          <span
            style={{ display: "inline-flex", alignItems: "center", gap: 10 }}
          >
            <span style={{ color: "var(--accent)" }}>
              <LothalMark size={22} />
            </span>
            <span className="serif" style={{ fontSize: 22 }}>
              Lothal
            </span>
            <span
              className="mono"
              style={{ fontSize: 11, color: "var(--ink-soft)" }}
            >
              v0.3
            </span>
          </span>
        }
        right={
          <span
            style={{ display: "inline-flex", alignItems: "center", gap: 18 }}
          >
            <span style={{ fontSize: 13.5, color: "var(--ink-mute)" }}>
              Docs
            </span>
            <Button variant={authed ? "accent" : "outline"} onClick={enter}>
              {authed ? "Open your workshop" : "Sign in"}
            </Button>
          </span>
        }
      />

      <main style={{ position: "relative", flex: 1, overflowY: "auto" }}>
        <div
          style={{
            position: "relative",
            zIndex: 1,
            boxSizing: "border-box",
            maxWidth: 1040,
            margin: "0 auto",
            padding: "0 28px 40px",
            display: "flex",
            flexDirection: "column",
            gap: 64,
          }}
        >
          {/* Hero — sits over its own harbor horizon. */}
          <section
            style={{
              position: "relative",
              padding: "72px 0 88px",
            }}
          >
            <HarborWatermark
              style={{ color: "var(--ink)" }}
              opacity={theme === "dark" ? 0.08 : 0.06}
            />
            <div style={{ position: "relative", maxWidth: 640 }}>
              <div className="label" style={{ color: "var(--accent)" }}>
                The drydock for software
              </div>
              <h1
                className="serif"
                style={{
                  marginTop: 12,
                  fontSize: 52,
                  lineHeight: 1.08,
                  letterSpacing: "-0.01em",
                }}
              >
                A conversation goes in.{" "}
                <span style={{ fontStyle: "italic", color: "var(--ink-soft)" }}>
                  A working codebase comes out.
                </span>
              </h1>
              <p
                style={{
                  marginTop: 16,
                  fontSize: 15.5,
                  lineHeight: 1.65,
                  color: "var(--ink-mute)",
                  maxWidth: 560,
                }}
              >
                Lothal asks until it understands what you mean, draws the
                sequence diagram you agree to, and only then writes the code.
                Built the way ships used to be — patiently, to spec.
              </p>
              <div
                style={{
                  marginTop: 26,
                  display: "flex",
                  gap: 10,
                  flexWrap: "wrap",
                }}
              >
                <Button variant="accent" size="lg" onClick={enter}>
                  {authed ? "Open your workshop" : "Enter the dockyard"}
                </Button>
                <Button variant="outline" size="lg" onClick={showJourney}>
                  See the journey
                </Button>
              </div>
            </div>
          </section>

          {/* The five-phase journey, straight from the shared phase metadata. */}
          <section
            id={JOURNEY_SECTION_ID}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 24,
              scrollMarginTop: 24,
            }}
          >
            <SectionHeading
              kicker="The journey"
              title={
                <>
                  Five phases.{" "}
                  <span style={{ fontStyle: "italic" }}>One keel.</span>
                </>
              }
              sub="Every project moves through the same patient sequence — and you steer at every step that matters."
            />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: 14,
              }}
            >
              {PHASES.map((p) => (
                <PhaseCard
                  key={p.id}
                  short={p.short}
                  label={p.label}
                  action={p.status.action}
                  copy={PHASE_COPY[p.id]}
                />
              ))}
            </div>
          </section>

          {/* The artifacts each build leaves behind. */}
          <section
            style={{ display: "flex", flexDirection: "column", gap: 24 }}
          >
            <SectionHeading
              kicker="What you get"
              title="Three artifacts, one truth."
              sub="Each phase leaves something you can read, question, and keep — not just a chat log."
            />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                gap: 14,
              }}
            >
              <ArtifactCard
                title="A spec in plain words"
                copy="The conversation distills into a PRD that says what you're building and why — before anything gets built."
              />
              <ArtifactCard
                title="A diagram you can argue with"
                copy="A living sequence diagram is the single source of truth for how the system behaves."
              />
              <ArtifactCard
                title="Code that matches it"
                copy="Generated only after you sign off, so what you read is what you meant."
              />
            </div>
          </section>

          {/* Closing call. */}
          <section
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              textAlign: "center",
              gap: 16,
              padding: "26px 0 8px",
              borderTop: "1px solid var(--border)",
            }}
          >
            <h2 className="serif" style={{ fontSize: 30, lineHeight: 1.2 }}>
              Lay the keel.
            </h2>
            <Button variant="accent" size="lg" onClick={enter}>
              {authed ? "Open your workshop" : "Enter the dockyard"}
            </Button>
          </section>

          <footer
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              flexWrap: "wrap",
              paddingTop: 20,
              borderTop: "1px solid var(--border)",
            }}
          >
            <span style={{ fontSize: 13, color: "var(--ink-soft)" }}>
              Lothal turns intent into implementation, one diagram at a time.
            </span>
            <span
              className="mono"
              style={{ fontSize: 11.5, color: "var(--ink-soft)" }}
            >
              built on langflow
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default function Landing() {
  return (
    <LothalSurface>
      <LandingView />
    </LothalSurface>
  );
}
