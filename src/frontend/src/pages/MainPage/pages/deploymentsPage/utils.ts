import { api } from "@/controllers/API/api";
import type { EnvVar } from "./constants";
import type { FlowHistoryListApiResponse } from "./types";

export const formatDateLabel = (value?: string | null): string => {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }

  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
};

export const mapProviderModeToLabel = (mode?: string): string => {
  if (mode === "both" || mode === "live") {
    return "Live";
  }
  return "Draft";
};

const inflightFlowHistoryRequests = new Map<
  string,
  Promise<FlowHistoryListApiResponse>
>();

export const fetchFlowHistoryWithDedupe = async (
  requestUrl: string,
): Promise<FlowHistoryListApiResponse> => {
  const existingRequest = inflightFlowHistoryRequests.get(requestUrl);
  if (existingRequest) {
    return existingRequest;
  }
  const request = api
    .get<FlowHistoryListApiResponse>(requestUrl)
    .then((response) => response.data)
    .finally(() => {
      inflightFlowHistoryRequests.delete(requestUrl);
    });
  inflightFlowHistoryRequests.set(requestUrl, request);
  return request;
};

export const validateEnvVars = (envVars: EnvVar[]): string[] => {
  const errors: string[] = [];
  const seenKeys = new Set<string>();

  envVars.forEach((item, index) => {
    const row = index + 1;
    const key = item.key.trim();
    const value = item.value.trim();

    if (!key && !value) {
      return;
    }

    if (!key) {
      errors.push(`Row ${row}: key is required when a value is provided.`);
      return;
    }

    if (!value) {
      errors.push(`Row ${row}: value is required for key "${key}".`);
      return;
    }

    if (seenKeys.has(key)) {
      errors.push(`Row ${row}: duplicate key "${key}". Keys must be unique.`);
      return;
    }
    seenKeys.add(key);
  });

  return errors;
};
