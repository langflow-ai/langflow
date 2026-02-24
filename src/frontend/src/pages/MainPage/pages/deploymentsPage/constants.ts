export const STATUS_DOT: Record<string, string> = {
  Healthy: "bg-green-500",
  Pending: "bg-yellow-400",
  Unhealthy: "bg-red-500",
};

export const TOGGLE_OPTIONS = [
  "Live Deployments",
  "Deployment Providers",
] as const;
export type DeploymentView = (typeof TOGGLE_OPTIONS)[number];

export const ATTACH_TABS = ["Flows", "Snapshots"] as const;
export type AttachTab = (typeof ATTACH_TABS)[number];

export const DEPLOYMENT_TYPES = ["Agent", "MCP"] as const;
export type DeploymentType = (typeof DEPLOYMENT_TYPES)[number];

export type ConfigMode = "reuse" | "create" | "modify";
export type KeyFormat = "assisted" | "auto" | "manual";
export type VariableScope = "coarse" | "granular";

export const TOTAL_STEPS = 5;
