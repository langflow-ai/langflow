import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

type GenerateComponentConfigResponse = {
  configured: boolean;
  missing: string[];
};

async function getGenerateComponentConfig(): Promise<GenerateComponentConfigResponse> {
  const response = await api.get<GenerateComponentConfigResponse>(
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
