/**
 * Flow deployment status constants
 */
export const DEPLOYMENT_STATUS = {
  DRAFT: "DRAFT",
  DEPLOYED: "DEPLOYED",
} as const;

export type DeploymentStatus =
  (typeof DEPLOYMENT_STATUS)[keyof typeof DEPLOYMENT_STATUS];

/**
 * Flow access type constants
 */
export const ACCESS_TYPE = {
  PRIVATE: "PRIVATE",
  PUBLIC: "PUBLIC",
  PROTECTED: "PROTECTED",
} as const;

export type AccessType = (typeof ACCESS_TYPE)[keyof typeof ACCESS_TYPE];
