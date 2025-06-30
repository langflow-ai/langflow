import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { AxiosResponse } from "axios";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TelemetryPreferenceRequest {
  enabled: boolean;
}

interface TelemetryPreferenceResponse {
  enabled: boolean;
}

interface VariableRead {
  id: string;
  name: string;
  value: string;
  category: string;
  type: string;
}

interface VariableCreate {
  name: string;
  value: string;
  category: string;
  type?: string;
  default_fields?: string[];
}

interface VariableUpdate {
  name?: string;
  value?: string;
  category?: string;
  type?: string;
  default_fields?: string[];
}

export const usePostTelemetryPreference: useMutationFunctionType<
  undefined,
  TelemetryPreferenceRequest
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postTelemetryPreferenceFunction = async ({
    enabled,
  }: TelemetryPreferenceRequest): Promise<
    AxiosResponse<TelemetryPreferenceResponse>
  > => {
    try {
      // First, try to get existing settings to see if enable_telemetry already exists
      const { data: existingVariables }: { data: VariableRead[] } =
        await api.get(`${getURL("VARIABLES")}/category/settings`);

      const telemetryVar = existingVariables.find(
        (variable) => variable.name === "enable_telemetry",
      );

      if (telemetryVar) {
        // Update existing variable
        const updateData: VariableUpdate = {
          value: enabled.toString(),
        };

        const response = await api.patch(
          `${getURL("VARIABLES")}/${telemetryVar.id}`,
          updateData,
        );

        return {
          ...response,
          data: { enabled },
        };
      } else {
        // Create new variable
        const createData: VariableCreate = {
          name: "enable_telemetry",
          value: enabled.toString(),
          category: "settings",
          type: "generic",
        };

        const response = await api.post(getURL("VARIABLES"), createData);

        return {
          ...response,
          data: { enabled },
        };
      }
    } catch (error) {
      console.error("Failed to update telemetry preference:", error);
      throw error;
    }
  };

  const mutation: UseMutationResult<
    AxiosResponse<TelemetryPreferenceResponse>,
    any,
    TelemetryPreferenceRequest
  > = mutate(["usePostTelemetryPreference"], postTelemetryPreferenceFunction, {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["telemetry-preference"] });
      queryClient.invalidateQueries({ queryKey: ["variables"] });
    },
    ...options,
  });

  return mutation;
};
