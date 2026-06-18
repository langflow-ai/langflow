// Shared lothal design-system atoms. Import from "@/pages/lothal/components".

export { ActorNode } from "./ActorNode";
export { AssistantQuestion } from "./AssistantQuestion";
export type { ButtonProps, ButtonSize, ButtonVariant } from "./Button";
export { Button } from "./Button";
export { CanvasLegend } from "./CanvasLegend";
export { CanvasPlaceholder } from "./CanvasPlaceholder";
export { CanvasSurface } from "./CanvasSurface";
export { ChatBubble } from "./ChatBubble";
export type { ChatComposerHandle } from "./ChatComposer";
export { ChatComposer } from "./ChatComposer";
export { ChatDock } from "./ChatDock";
export { CodeView } from "./CodeView";
export { D2Canvas } from "./D2Canvas";
export { DiagramCanvas } from "./DiagramCanvas";
export type { Anchor } from "./d2/anchor";
export { decodeElementId, resolveAnchor } from "./d2/anchor";
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
