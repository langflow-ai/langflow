import useAuthStore from "@/stores/authStore";
import { useQueryFunctionType } from "@/types/api";
import { UseQueryResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface VariableRead {
  id: string;
  name: string;
  value: string;
  category: string;
  type: string;
}

interface TelemetryPreferenceResponse {
  enabled: boolean;
}

export const useGetTelemetryPreference: useQueryFunctionType<
  undefined,
  TelemetryPreferenceResponse
> = (options?) => {
  const { query } = UseRequestProcessor();

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const getTelemetryPreferenceFn =
    async (): Promise<TelemetryPreferenceResponse> => {
      if (!isAuthenticated) return { enabled: true }; // Default to enabled for unauthenticated users

      try {
        // Use the generic variables endpoint to get settings category
        const { data }: { data: VariableRead[] } = await api.get(
          `${getURL("VARIABLES")}/category/settings`,
        );

        // Find the enable_telemetry variable
        const telemetryVar = data.find(
          (variable) => variable.name === "enable_telemetry",
        );

        // Return the value, defaulting to true if not found
        return {
          enabled:
            telemetryVar?.value === "true" || telemetryVar?.value === undefined,
        };
      } catch (error) {
        console.warn(
          "Failed to get telemetry preference, defaulting to enabled:",
          error,
        );
        return { enabled: true };
      }
    };

  const queryResult: UseQueryResult<TelemetryPreferenceResponse> = query({
    queryKey: ["telemetry-preference"],
    queryFn: getTelemetryPreferenceFn,
    enabled: isAuthenticated,
    ...options,
  });

  return queryResult;
};
