// Structurally compatible with `FlowPersistenceNode` so a node can cross
// between the persistence barrier and this policy without a cast.
export type LoopbackNode = {
  id?: string;
  type?: string;
  data?: {
    type?: string;
    node?: {
      template?: Record<string, unknown>;
    };
  };
};

export type LoopbackFlowData = {
  nodes?: LoopbackNode[];
  [key: string]: unknown;
};

export type LoopbackExample = {
  data?: LoopbackFlowData;
  [key: string]: unknown;
};

export const LOOPBACK_OPENAI_BASE_URL: string;
export const LOOPBACK_OPENAI_API_KEY: string;
export const LOOPBACK_MODEL: {
  id: string;
  name: string;
  icon: string;
  provider: string;
  category: string;
  metadata: Record<string, unknown>;
};

export function isLoopbackTarget(node: LoopbackNode): boolean;
export function withLoopbackTemplate(node: LoopbackNode): LoopbackNode;
export function isNodeLoopbackConfigured(node: LoopbackNode): boolean;
export function applyLoopbackToFlowData(data: LoopbackFlowData): {
  data: LoopbackFlowData;
  targetNodeIds: string[];
};
export function isFlowDataLoopbackConfigured(data: LoopbackFlowData): boolean;
export function applyLoopbackToExamples(
  examples: LoopbackExample[],
): LoopbackExample[];
