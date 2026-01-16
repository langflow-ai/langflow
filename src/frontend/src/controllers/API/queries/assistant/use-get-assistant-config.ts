import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { AssistantConfigResponse } from "@/components/core/assistant/assistant.types";

const STALE_TIME_MS = 5 * 60 * 1000;

async function getAssistantConfig(): Promise<AssistantConfigResponse> {
  const response = await api.get<AssistantConfigResponse>(
    getURL("ASSISTANT_CHECK_CONFIG"),
  );
  return response.data;
}

export function useGetAssistantConfig() {
  return useQuery({
    queryKey: ["useGetAssistantConfig"],
    queryFn: getAssistantConfig,
    staleTime: STALE_TIME_MS,
  });
}
