export type FlowPersistenceNode = {
  type?: string;
  data?: {
    node?: {
      template?: Record<string, unknown>;
    };
  };
};

export type FlowPersistenceData = {
  nodes?: FlowPersistenceNode[];
  [key: string]: unknown;
};

export function isMatchingFullFlowAutosavePayload(
  value: unknown,
  matchesData: (data: FlowPersistenceData) => boolean,
): boolean;
export function isModelRefreshBody(value: unknown): boolean;
export function modelRefreshFlowId(value: unknown): string | undefined;
export function canTrackFullFlowAutosavePayload(
  value: unknown,
  matchesData: (data: FlowPersistenceData) => boolean,
  observedModelRefreshes: number,
  expectedModelRefreshes: number,
): boolean;
export function isFlowPersistenceBarrierSatisfied(
  autosaveFinished: boolean,
  completedModelRefreshes: number,
  requiredModelRefreshes: number,
): boolean;
export function modelRefreshNodeCount(data: FlowPersistenceData): number;
export function requiresPostRefreshAutosave(data: FlowPersistenceData): boolean;
