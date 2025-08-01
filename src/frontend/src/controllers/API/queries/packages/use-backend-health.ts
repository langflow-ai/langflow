import { useQuery } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { BASE_URL_API } from "@/constants/constants";
import { api } from "../../api";

export interface HealthResponse {
  status: string;
  chat: string;
  db: string;
}

async function checkBackendHealth(): Promise<HealthResponse> {
  const response = await api.get(
    `${BASE_URL_API.replace("/api/v1", "")}/health_check`,
  );
  return response.data;
}

export const useBackendHealth = (
  enabled: boolean = true,
  refetchInterval: number = 5000,
) => {
  return useQuery<HealthResponse, AxiosError>({
    queryKey: ["backend-health"],
    queryFn: checkBackendHealth,
    enabled,
    refetchInterval,
    retry: 0,
    refetchOnWindowFocus: false,
  });
};
