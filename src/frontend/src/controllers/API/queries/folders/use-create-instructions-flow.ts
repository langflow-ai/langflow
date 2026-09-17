import { useQueryClient } from "@tanstack/react-query";
import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

/** Prepare the contract baseline, then use ordinary flow creation and its guards. */
export function useCreateProjectFlow() {
  const { mutateAsync: createFlow } = usePostAddFlow();
  const queryClient = useQueryClient();
  return async (
    projectId: string,
    fieldName: string,
    initialValue = "",
    initialConfig?: Record<string, unknown>,
  ) => {
    const { data } = await api.post<FlowType>(
      `${getURL("PROJECTS")}/${projectId}/flow-baseline`,
      {
        initial_value: initialValue,
        ...(initialConfig ? { initial_config: initialConfig } : {}),
      },
      { params: { field_name: fieldName } },
    );
    const flow = await createFlow({
      ...data,
      data: data.data!,
      folder_id: projectId,
      is_component: false,
      endpoint_name: undefined,
      icon: undefined,
      gradient: undefined,
      tags: undefined,
      mcp_enabled: false,
    });
    void queryClient.invalidateQueries({
      queryKey: ["useGetProjectFlowOutputs", projectId, fieldName],
    });
    void queryClient.invalidateQueries({
      queryKey: ["useGetProjectFlows", projectId],
    });
    return flow;
  };
}

export const useCreateInstructionsFlow = useCreateProjectFlow;
