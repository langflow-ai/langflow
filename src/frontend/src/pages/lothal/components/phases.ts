// Phase metadata for the lothal surface — the frontend's single source of
// truth for phase ids, presentation, and predicates. Drives the PhaseStepper
// and StatusDot atoms, the Dashboard card status, and the Workspace pane
// switch.

// The lothal phases, in order. Keep in sync with the backend contract:
// src/backend/base/langflow/lothal/schemas.py (`Phase` Literal) — the two
// sides can't share code across languages. Epic E.2 merged the two diagram
// phases (DIAGRAM_GENERATION + DIAGRAM_REFINEMENT) into one ARCHITECTURE stage;
// Epic UI (U.8) inserts the PROTOTYPE stage between ARCHITECTURE and
// CODE_GENERATION (the Open Design prototype stage); Epic U-PLAN inserts the PLAN
// stage (the verification-driven PM tree) after PROTOTYPE.
export const PHASE_IDS = [
  "CLARIFICATION",
  "ARCHITECTURE",
  "PROTOTYPE",
  "PLAN",
  "CODE_GENERATION",
  "DONE",
] as const;

export type LothalPhaseId = (typeof PHASE_IDS)[number];

export type PhaseStatus = {
  /** Card-footer status line ("needs your input"). */
  text: string;
  /** True for phases waiting on the user — rendered in accent. */
  action: boolean;
};

export type PhaseMeta = {
  id: LothalPhaseId;
  label: string;
  short: string;
  status: PhaseStatus;
};

export const PHASES: PhaseMeta[] = [
  {
    id: "CLARIFICATION",
    label: "Clarify",
    short: "01",
    status: { text: "needs your input", action: true },
  },
  {
    id: "ARCHITECTURE",
    label: "Design",
    short: "02",
    status: { text: "needs your review", action: true },
  },
  {
    id: "PROTOTYPE",
    label: "Prototype",
    short: "03",
    status: { text: "shaping the prototype", action: true },
  },
  {
    id: "PLAN",
    label: "Plan",
    short: "04",
    status: { text: "needs your review", action: true },
  },
  {
    id: "CODE_GENERATION",
    label: "Generate",
    short: "05",
    status: { text: "writing the code", action: false },
  },
  {
    id: "DONE",
    label: "Deliver",
    short: "06",
    status: { text: "ready to deliver", action: false },
  },
];

export function phaseIndex(phase: string): number {
  return PHASES.findIndex((p) => p.id === phase);
}

/** Short design label for a phase ("Refine"), or the raw id if unknown. */
export function phaseLabel(phase: string): string {
  return PHASES.find((p) => p.id === phase)?.label ?? phase;
}

/** Card-footer status for a phase; a generic line for unknown phases. */
export function phaseStatus(phase: string): PhaseStatus {
  return (
    PHASES.find((p) => p.id === phase)?.status ?? {
      text: "in progress",
      action: false,
    }
  );
}

/** From code generation onward the code surface takes over the canvas pane. */
export function isCodePhase(phase: string): boolean {
  return phase === "CODE_GENERATION" || phase === "DONE";
}
