import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { AssistantConfigResponse } from "@/components/core/generateComponent/types";

async function getGenerateComponentConfig(): Promise<AssistantConfigResponse> {
  const response = await api.get<AssistantConfigResponse>(
    getURL("GENERATE_COMPONENT_CHECK_CONFIG"),
  );
  return response.data;
}

export function useGetGenerateComponentConfig() {
  return useQuery({
    queryKey: ["useGetGenerateComponentConfig"],
    queryFn: getGenerateComponentConfig,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}
