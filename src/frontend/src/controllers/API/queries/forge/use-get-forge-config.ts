import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

type ForgeConfigResponse = {
  configured: boolean;
  missing: string[];
};

async function getForgeConfig(): Promise<ForgeConfigResponse> {
  const response = await api.get<ForgeConfigResponse>(
    getURL("FORGE_CHECK_CONFIG"),
  );
  return response.data;
}

export function useGetForgeConfig() {
  return useQuery({
    queryKey: ["useGetForgeConfig"],
    queryFn: getForgeConfig,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}
