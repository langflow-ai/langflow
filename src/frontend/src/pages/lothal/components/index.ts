// Shared lothal design-system atoms. Import from "@/pages/lothal/components".

export { ActorNode } from "./ActorNode";
export { AssistantQuestion } from "./AssistantQuestion";
export type { ButtonProps, ButtonSize, ButtonVariant } from "./Button";
export { Button } from "./Button";
export { CanvasLegend } from "./CanvasLegend";
export { CanvasPlaceholder } from "./CanvasPlaceholder";
export { CanvasSurface } from "./CanvasSurface";
export { ChatBubble } from "./ChatBubble";
export { ChatDock } from "./ChatDock";
export { CodeView } from "./CodeView";
export { DiagramCanvas } from "./DiagramCanvas";
export { compileD2, type D2Compiled } from "./d2/render";
export { EmptyHint } from "./EmptyHint";
export { LothalMark } from "./LothalMark";
export {
  isNotImplemented,
  NotReady,
  notImplementedDetail,
} from "./NotReady";
export { PhaseStepper, type PhaseStepperStyle } from "./PhaseStepper";
export {
  isCodePhase,
  type LothalPhaseId,
  PHASE_IDS,
  PHASES,
  type PhaseMeta,
  type PhaseStatus,
  phaseIndex,
  phaseLabel,
  phaseStatus,
} from "./phases";
export { StatusDot } from "./StatusDot";
export { SystemBlock } from "./SystemBlock";
export {
  highlightTokens,
  type Language,
  languageFromPath,
  type Token,
  type TokenType,
} from "./syntax";
export { TopBar } from "./TopBar";
export { LOTHAL_VERSION } from "./version";
