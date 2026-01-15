import {
  RATE_LIMIT_PATTERNS,
  PROVIDER_ERROR_PATTERNS,
  QUOTA_ERROR_PATTERNS,
} from "../assistant.constants";

export type ErrorCategory = "rate_limit" | "quota" | "provider" | "generic";

export const categorizeError = (
  errorMessage: string,
  statusCode?: number,
): ErrorCategory => {
  const errorLower = errorMessage.toLowerCase();

  if (RATE_LIMIT_PATTERNS.some((pattern) => errorLower.includes(pattern))) {
    return "rate_limit";
  }
  if (QUOTA_ERROR_PATTERNS.some((pattern) => errorLower.includes(pattern))) {
    return "quota";
  }
  if (PROVIDER_ERROR_PATTERNS.some((pattern) => errorLower.includes(pattern))) {
    return "provider";
  }
  if (statusCode === 400 && errorLower.includes("required")) {
    return "provider";
  }
  return "generic";
};
