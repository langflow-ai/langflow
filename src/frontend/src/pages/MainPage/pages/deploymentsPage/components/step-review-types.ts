export interface ReviewEnvVar {
  key: string;
  masked: string;
}

export interface ReviewConnectionDetail {
  name: string;
  isNew: boolean;
  envVars: ReviewEnvVar[];
}

export interface ReviewFlowItem {
  flowId: string;
  flowName: string;
  toolName: string;
  versionLabel: string;
  connectionDetails: ReviewConnectionDetail[];
}

export interface RemovedReviewFlowItem {
  flowId: string;
  flowName: string;
}
