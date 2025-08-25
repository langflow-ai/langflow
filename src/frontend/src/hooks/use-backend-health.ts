import { useQuery } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import { api } from "@/controllers/API/api";

async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await api.get(`${BASE_URL_API}health`, {
      timeout: 3000,
    });
    return response.status === 200;
  } catch (error: any) {
    console.log("Backend health check failed:", error.code || error.message);
    return false;
  }
}

export const useBackendHealth = (enabled: boolean = true) => {
  return useQuery({
    queryKey: ["backend-health"],
    queryFn: checkBackendHealth,
    refetchInterval: enabled ? 1500 : false,
    retry: false,
    staleTime: 0,
    refetchOnWindowFocus: false,
    refetchOnMount: true,
    enabled,
  });
};
