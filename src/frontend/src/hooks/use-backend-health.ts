import { useQuery } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import { api } from "@/controllers/API/api";

async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await api.get(`${BASE_URL_API}health`, {
      timeout: 3000, // 3 second timeout for faster detection
    });
    return response.status === 200;
  } catch (error: any) {
    // Log the error type for debugging
    console.log("Backend health check failed:", error.code || error.message);
    return false;
  }
}

export const useBackendHealth = (enabled: boolean = true) => {
  return useQuery({
    queryKey: ["backend-health"],
    queryFn: checkBackendHealth,
    refetchInterval: enabled ? 1500 : false, // Check every 1.5 seconds for faster detection
    retry: false, // Don't retry failed requests
    staleTime: 0, // Always refetch
    refetchOnWindowFocus: false, // Don't refetch on window focus
    refetchOnMount: true, // Always refetch on mount
    enabled,
  });
};
