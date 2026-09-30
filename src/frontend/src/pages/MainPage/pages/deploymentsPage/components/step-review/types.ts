export interface ReviewConnectionEnvVar {
  key: string;
  masked: string;
}

export interface ReviewConnectionDetail {
  name: string;
  isNew: boolean;
  envVars: ReviewConnectionEnvVar[];
}

export interface ReviewFlowItem {
  attachmentKey: string;
  flowId: string;
  flowName: string;
  toolName: string;
  defaultToolName: string;
  versionLabel: string;
  connectionDetails: ReviewConnectionDetail[];
  wxoEligibilityIssue: WatsonxFlowEligibilityIssue | undefined;
}

import type { WatsonxFlowEligibilityIssue } from "../../helpers/watsonx-flow-eligibility";
