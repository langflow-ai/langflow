import { ErrorLogType } from "../api";

export function isErrorLogType(value: any): value is ErrorLogType {
  return (
    typeof value === "object" &&
    value !== null &&
    "errorMessage" in value &&
    typeof value.errorMessage === "string" &&
    "stackTrace" in value &&
    typeof value.stackTrace === "string"
  );
}

export function isErrorLog(
  log: any,
): log is { type: "error"; message: ErrorLogType } {
  return (
    typeof log === "object" &&
    log !== null &&
    (log.type === "error" || log.type === "ValueError") &&
    isErrorLogType(log.message)
  );
}
