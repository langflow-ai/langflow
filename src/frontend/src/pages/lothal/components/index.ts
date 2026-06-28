// Shared lothal design-system atoms. Import from "@/pages/lothal/components".

// NB: <ArtifactsPane> is intentionally NOT re-exported here. It pulls in
// react-markdown (ESM), which Jest doesn't transform; routing it through this
// barrel would force every component-barrel consumer's test to mock markdown.
// Import it directly from "./ArtifactsPane" (the Workspace does).
export { AssistantQuestion } from "./AssistantQuestion";
export {
  ADR_PATH,
  type ArtifactKind,
  type ArtifactTab,
  artifactKind,
  artifactLabel,
  orderArtifacts,
} from "./artifacts";
export type { ButtonProps, ButtonSize, ButtonVariant } from "./Button";
export { Button } from "./Button";
export { CanvasPlaceholder } from "./CanvasPlaceholder";
export { ChatBubble } from "./ChatBubble";
export type { ChatComposerHandle } from "./ChatComposer";
export { ChatComposer } from "./ChatComposer";
export { ChatDock } from "./ChatDock";
export { CodeView } from "./CodeView";
export { D2Canvas } from "./D2Canvas";
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
export {
  SampleDiagram,
  type SampleMessage,
  type SampleParticipant,
} from "./SampleDiagram";
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
