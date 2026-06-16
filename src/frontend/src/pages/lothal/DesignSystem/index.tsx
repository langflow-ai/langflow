// Lothal design-system gallery (not in nav; reachable at /lothal/design-system).
// Exercises every B.1 atom in light + dark + density, and renders the NotReady
// state from a sample structured 501 — the B.1 verification surface.

import { type ReactNode, useState } from "react";
import type {
  DiagramEdge,
  DiagramNode,
} from "@/controllers/API/queries/lothal";
import {
  AssistantQuestion,
  Button,
  CanvasPlaceholder,
  ChatBubble,
  ChatDock,
  CodeView,
  DiagramCanvas,
  EmptyHint,
  LothalMark,
  NotReady,
  PHASES,
  PhaseStepper,
  type PhaseStepperStyle,
  StatusDot,
  SystemBlock,
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

// A seeded `/diagram` payload — the same shape the endpoint returns once live
// (Epic 2.3). It exercises both node types and all three edge kinds, and is how
// the B.4 canvas is verified visually while /diagram is still a 501 stub.
const SAMPLE_NODES: DiagramNode[] = [
  {
    id: "user",
    type: "actorNode",
    position: { x: 40, y: 150 },
    data: { label: "User" },
  },
  {
    id: "chat",
    type: "systemNode",
    position: { x: 280, y: 60 },
    data: { label: "Chat Interface" },
  },
  {
    id: "llm",
    type: "systemNode",
    position: { x: 560, y: 60 },
    data: { label: "LLM Engine", note: "Claude" },
  },
  {
    id: "store",
    type: "systemNode",
    position: { x: 560, y: 250 },
    data: { label: "Spec Store", kind: "data" },
  },
];
const SAMPLE_EDGES: DiagramEdge[] = [
  {
    id: "e1",
    source: "user",
    target: "chat",
    data: { order: 1, label: "submit spec", kind: "sync" },
  },
  {
    id: "e2",
    source: "chat",
    target: "llm",
    data: { order: 2, label: "clarify", kind: "sync" },
  },
  {
    id: "e3",
    source: "llm",
    target: "chat",
    data: { order: 3, label: "questions", kind: "return" },
  },
  {
    id: "e4",
    source: "chat",
    target: "store",
    data: { order: 4, label: "persist spec", kind: "async" },
  },
  {
    id: "e5",
    source: "chat",
    target: "user",
    data: { order: 5, label: "ask", kind: "return" },
  },
];

// A sample `/code` payload — the shape the contract returns — so the populated
// CodeView is visually verifiable while `/code` is still a 501 stub.
const SAMPLE_FILES = [
  {
    path: "app/main.py",
    content: `# Tide Tracker — FastAPI entrypoint
from fastapi import FastAPI

from app.routes import tides

app = FastAPI(title="Tide Tracker")
app.include_router(tides.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
`,
  },
  {
    path: "app/routes/tides.py",
    content: `from fastapi import APIRouter

router = APIRouter(prefix="/tides", tags=["tides"])

BREAKS = ["mavericks", "ocean-beach", "pacifica"]


@router.get("/")
async def list_breaks() -> list[str]:
    """Return the surf breaks we track."""
    return BREAKS
`,
  },
  {
    path: "frontend/index.html",
    content: `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Tide Tracker</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/main.js"></script>
  </body>
</html>
`,
  },
  {
    path: "README.md",
    content: `# Tide Tracker

A small app that tracks tide windows for a handful of surf breaks.

## Run

    uvicorn app.main:app --reload
`,
  },
];

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

// The B.3 chat atoms, exercised with sample data. They render the same way
// from real `/messages` data once the clarification backend (Epic 1) is live —
// this is how they're verified while that endpoint is still a 501 stub.
function ChatShowcase() {
  const [draft, setDraft] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 14,
        width: "100%",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          maxWidth: 520,
        }}
      >
        <ChatBubble
          role="USER"
          content="I want a tide-tracking app for surfers."
        />
        <ChatBubble
          role="ASSISTANT"
          content="Got it. Who's the primary user — casual beachgoers, or serious surfers tracking specific breaks?"
        >
          <AssistantQuestion
            suggestions={["Casual beachgoers", "Serious surfers", "Both"]}
            onPick={setPicked}
          />
        </ChatBubble>
        <SystemBlock>Requirements clear — sketching the diagram</SystemBlock>
        <ChatBubble
          role="ASSISTANT"
          content="Drafting the sequence diagram now"
          streaming
        />
        {picked && (
          <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
            picked: <span style={{ color: "var(--accent-ink)" }}>{picked}</span>
          </span>
        )}
      </div>
      <div
        style={{
          maxWidth: 520,
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          overflow: "hidden",
        }}
      >
        <ChatDock
          value={draft}
          onChange={setDraft}
          onSend={() => setDraft("")}
        />
      </div>
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
              title="No projects yet"
              sub="Describe what you want to build and a new project takes shape here."
              kbd="N to start"
            />
          </div>
        </Section>

        <Section title="Chat (bubbles · chips · transition · dock)">
          <ChatShowcase />
        </Section>

        <Section title="Canvas — sequence diagram (seeded /diagram payload)">
          <div
            style={{
              width: "100%",
              height: 380,
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              overflow: "hidden",
            }}
          >
            <DiagramCanvas nodes={SAMPLE_NODES} edges={SAMPLE_EDGES} />
          </div>
        </Section>

        <Section title="Canvas placeholder (no diagram yet)">
          <div style={{ width: "100%", minHeight: 260 }}>
            <CanvasPlaceholder phase="CLARIFICATION" />
          </div>
        </Section>

        <Section title="Code view (tree · tabs · highlight · delivery)">
          <div
            style={{
              width: "100%",
              height: 420,
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              overflow: "hidden",
            }}
          >
            <CodeView files={SAMPLE_FILES} />
          </div>
        </Section>

        <Section title="Settings — appearance toggles (persisted)">
          <div
            style={{
              width: "100%",
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            <p style={{ fontSize: 13, color: "var(--ink-mute)", margin: 0 }}>
              The settings page (/lothal/settings) renders these toggles via{" "}
              <span className="mono">useLothalTheme()</span>; the choice is
              saved to localStorage so it survives reloads.
            </p>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span
                className="mono"
                style={{ fontSize: 10, width: 60, color: "var(--ink-soft)" }}
              >
                theme
              </span>
              {(["light", "dark"] as const).map((t) => (
                <Button
                  key={t}
                  size="sm"
                  variant={theme === t ? "accent" : "outline"}
                  onClick={() => setTheme(t)}
                  style={{ textTransform: "capitalize" }}
                >
                  {t}
                </Button>
              ))}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span
                className="mono"
                style={{ fontSize: 10, width: 60, color: "var(--ink-soft)" }}
              >
                density
              </span>
              {(["compact", "regular", "comfy"] as LothalDensity[]).map((d) => (
                <Button
                  key={d}
                  size="sm"
                  variant={density === d ? "accent" : "outline"}
                  onClick={() => setDensity(d)}
                  style={{ textTransform: "capitalize" }}
                >
                  {d}
                </Button>
              ))}
            </div>
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
