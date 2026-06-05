// Shared phase presentation for the lothal surface. Single source of truth so
// Dashboard and Workspace never drift (e.g. "Refining" vs "Refining Diagram").

export const PHASE_LABELS: Record<string, string> = {
  CLARIFICATION: "Clarifying",
  DIAGRAM_GENERATION: "Generating Diagram",
  DIAGRAM_REFINEMENT: "Refining Diagram",
  CODE_GENERATION: "Generating Code",
  DONE: "Done",
};

export const PHASE_COLORS: Record<string, string> = {
  CLARIFICATION: "bg-blue-100 text-blue-700",
  DIAGRAM_GENERATION: "bg-yellow-100 text-yellow-700",
  DIAGRAM_REFINEMENT: "bg-purple-100 text-purple-700",
  CODE_GENERATION: "bg-orange-100 text-orange-700",
  DONE: "bg-green-100 text-green-700",
};
