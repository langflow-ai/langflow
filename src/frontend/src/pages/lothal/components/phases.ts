// Phase metadata for the lothal design system, ported from the design bundle.
// Drives the PhaseStepper and StatusDot atoms.
//
// Note: this is the *design* presentation (short verbs: Clarify/Sketch/…),
// distinct from constants.ts `PHASE_LABELS` which the current B.0 screens use.
// B.2/B.3 reconcile the screens onto these atoms.

export type LothalPhaseId =
  | "CLARIFICATION"
  | "DIAGRAM_GENERATION"
  | "DIAGRAM_REFINEMENT"
  | "CODE_GENERATION"
  | "DONE";

export type PhaseMeta = {
  id: LothalPhaseId;
  label: string;
  short: string;
};

export const PHASES: PhaseMeta[] = [
  { id: "CLARIFICATION", label: "Clarify", short: "01" },
  { id: "DIAGRAM_GENERATION", label: "Sketch", short: "02" },
  { id: "DIAGRAM_REFINEMENT", label: "Refine", short: "03" },
  { id: "CODE_GENERATION", label: "Generate", short: "04" },
  { id: "DONE", label: "Deliver", short: "05" },
];

export function phaseIndex(phase: string): number {
  return PHASES.findIndex((p) => p.id === phase);
}

/** Short design label for a phase ("Refine"), or the raw id if unknown. */
export function phaseLabel(phase: string): string {
  return PHASES.find((p) => p.id === phase)?.label ?? phase;
}
