export const STATUS_DOT: Record<string, string> = {
  Healthy: "bg-green-500",
  Pending: "bg-yellow-400",
  Unhealthy: "bg-red-500",
};

export const DEPLOYMENT_TYPES = ["Agent", "MCP"] as const;
export type DeploymentType = (typeof DEPLOYMENT_TYPES)[number];

export type EnvVar = {
  key: string;
  value: string;
  globalVar?: boolean;
  // Optional backend credential key; lets UI display a friendlier key label.
  deploymentKey?: string;
};

export type VariableScope = "coarse" | "granular";

export const TOTAL_STEPS = 5;
