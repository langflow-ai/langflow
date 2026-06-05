// Lothal design-system gallery (not in nav; reachable at /lothal/design-system).
// Exercises every B.1 atom in light + dark + density, and renders the NotReady
// state from a sample structured 501 — the B.1 verification surface.

import { type ReactNode, useState } from "react";
import {
  Button,
  EmptyHint,
  LothalMark,
  NotReady,
  PHASES,
  PhaseStepper,
  type PhaseStepperStyle,
  StatusDot,
  TopBar,
} from "../components";
import {
  type LothalDensity,
  LothalSurface,
  useLothalTheme,
} from "../theme/LothalSurface";

// A representative structured-501 response, as the contract returns it.
const SAMPLE_501 = {
  response: {
    status: 501,
    data: {
      detail: "Code generation isn't built yet.",
      status: "not_implemented",
    },
  },
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="label">{title}</div>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 16,
          padding: 16,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
        }}
      >
        {children}
      </div>
    </section>
  );
}

function Swatch({ token }: { token: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 8,
          background: `var(${token})`,
          border: "1px solid var(--border-strong)",
        }}
      />
      <span
        className="mono"
        style={{ fontSize: 9.5, color: "var(--ink-soft)" }}
      >
        {token}
      </span>
    </div>
  );
}

function Gallery() {
  const { theme, setTheme, density, setDensity } = useLothalTheme();
  const [stepperPhase, setStepperPhase] =
    useState<string>("DIAGRAM_REFINEMENT");

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
              Lothal design system
            </span>
          </span>
        }
        right={
          <span style={{ display: "inline-flex", gap: 8 }}>
            <Button
              variant={theme === "light" ? "accent" : "outline"}
              size="sm"
              onClick={() => setTheme("light")}
            >
              Light
            </Button>
            <Button
              variant={theme === "dark" ? "accent" : "outline"}
              size="sm"
              onClick={() => setTheme("dark")}
            >
              Dark
            </Button>
          </span>
        }
      />

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 28,
          maxWidth: 980,
        }}
      >
        <Section title="Density">
          {(["compact", "regular", "comfy"] as LothalDensity[]).map((d) => (
            <Button
              key={d}
              size="sm"
              variant={density === d ? "accent" : "outline"}
              onClick={() => setDensity(d)}
            >
              {d}
            </Button>
          ))}
        </Section>

        <Section title="Palette tokens">
          {[
            "--paper",
            "--surface",
            "--surface-2",
            "--ink",
            "--accent",
            "--accent-ink",
            "--success",
            "--warn",
          ].map((token) => (
            <Swatch key={token} token={token} />
          ))}
        </Section>

        <Section title="Buttons — variants">
          <Button variant="primary">Primary</Button>
          <Button variant="accent">Accent</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="accent" disabled>
            Disabled
          </Button>
        </Section>

        <Section title="Buttons — sizes">
          <Button size="sm" variant="primary">
            Small
          </Button>
          <Button size="md" variant="primary">
            Medium
          </Button>
          <Button size="lg" variant="primary">
            Large
          </Button>
        </Section>

        <Section title="Status dots (per phase)">
          {PHASES.map((p) => (
            <StatusDot key={p.id} phase={p.id} />
          ))}
        </Section>

        <Section title="Phase stepper">
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 14,
              width: "100%",
            }}
          >
            <div style={{ display: "flex", gap: 6 }}>
              {PHASES.map((p) => (
                <Button
                  key={p.id}
                  size="sm"
                  variant={stepperPhase === p.id ? "accent" : "outline"}
                  onClick={() => setStepperPhase(p.id)}
                >
                  {p.label}
                </Button>
              ))}
            </div>
            {(["stepper", "pill", "breadcrumb"] as PhaseStepperStyle[]).map(
              (v) => (
                <div
                  key={v}
                  style={{ display: "flex", alignItems: "center", gap: 12 }}
                >
                  <span
                    className="mono"
                    style={{
                      fontSize: 10,
                      width: 80,
                      color: "var(--ink-soft)",
                    }}
                  >
                    {v}
                  </span>
                  <PhaseStepper phase={stepperPhase} variant={v} />
                </div>
              ),
            )}
          </div>
        </Section>

        <Section title="Logo mark">
          {[18, 28, 44].map((s) => (
            <span key={s} style={{ color: "var(--accent)" }}>
              <LothalMark size={s} />
            </span>
          ))}
        </Section>

        <Section title="Empty hint">
          <div style={{ width: "100%" }}>
            <EmptyHint
              title="No vessels in the harbor"
              sub="Describe what you want to build and a new project takes shape here."
              kbd="N to start"
            />
          </div>
        </Section>

        <Section title="NotReady (from a structured 501)">
          <div style={{ width: "100%", minHeight: 220 }}>
            <NotReady title="Not ready yet" error={SAMPLE_501} />
          </div>
        </Section>
      </div>
    </div>
  );
}

export default function DesignSystem() {
  return (
    <LothalSurface>
      <Gallery />
    </LothalSurface>
  );
}
