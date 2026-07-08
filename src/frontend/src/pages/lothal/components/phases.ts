// Phase metadata for the lothal surface — the frontend's single source of
// truth for phase ids, presentation, and predicates. Drives the PhaseStepper
// and StatusDot atoms, the Dashboard card status, and the Workspace pane
// switch.

// The lothal *UI* phases, in order. These drive the stepper, StatusDot, and the
// Workspace pane switch. They mostly mirror the backend `ProjectPhase`, with one
// deliberate divergence (ReviewPane, Part B): the backend's CODE_GENERATION phase is
// presented as the REVIEW stage. Generation is launched from the Plan pane and runs
// in the backend; there is no separate "Generate" UI stage — while codegen runs the
// user reviews the committed code in the ReviewPane. `uiPhase()` maps a backend phase
// onto this list; use it wherever a project's raw `phase` feeds phase positioning.
//
// (History: Epic E.2 merged the two diagram phases into ARCHITECTURE; Epic UI U.8
// inserted PROTOTYPE; Epic U-PLAN inserted PLAN; Part B replaces the Generate UI
// stage with REVIEW.)
export const PHASE_IDS = [
  "CLARIFICATION",
  "ARCHITECTURE",
  "PROTOTYPE",
  "PLAN",
  "REVIEW",
  "DONE",
] as const;

export type LothalPhaseId = (typeof PHASE_IDS)[number];

/**
 * Map a backend project phase onto the UI phase list. The backend still transitions
 * a project into CODE_GENERATION (codegen is a backend stage launched from the Plan
 * pane); the UI presents that as the REVIEW stage. Every other phase passes through.
 * Use this wherever a raw `project.phase` is fed to `phaseIndex` / the stepper /
 * StatusDot, so CODE_GENERATION resolves to a valid UI index instead of -1.
 */
export function uiPhase(phase: string): string {
  return phase === "CODE_GENERATION" ? "REVIEW" : phase;
}

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
    id: "REVIEW",
    label: "Review",
    short: "05",
    status: { text: "reviewing the code", action: true },
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

/** The code-review stage (Part B): the ReviewPane takes over the right pane.
 * Accepts either the UI id (REVIEW) or the backend phase it maps from
 * (CODE_GENERATION), so callers can pass a raw `project.phase`. */
export function isReviewPhase(phase: string): boolean {
  return uiPhase(phase) === "REVIEW";
}
