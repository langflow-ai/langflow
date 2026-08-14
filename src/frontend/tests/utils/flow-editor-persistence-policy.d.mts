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
export function canAcceptFullFlowAutosavePayload(
  value: unknown,
  matchesData: (data: FlowPersistenceData) => boolean,
  completedModelRefreshes: number,
  expectedModelRefreshes: number,
): boolean;
export function modelRefreshNodeCount(data: FlowPersistenceData): number;
export function requiresPostRefreshAutosave(data: FlowPersistenceData): boolean;
