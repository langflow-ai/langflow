import type { FlowHistoryEntry } from "@/types/flow/history";

export type CheckpointAttachItem = {
  id: string;
  name: string;
  updatedDate: string;
};

export type FlowCheckpointGroup = {
  flowId: string;
  flowName: string;
  checkpoints: CheckpointAttachItem[];
};

export type FlowHistoryListApiResponse = {
  entries: FlowHistoryEntry[];
};

export type DeploymentCreationState = "idle" | "creating" | "success" | "error";

export type TestDeploymentTarget = {
  id: string;
  name: string;
  deploymentType: "agent" | "mcp";
  mode?: string;
};

export type CreatedDeploymentUiMeta = {
  deploymentId: string;
  attachedCount: number;
  createdAt: string;
};
