import { useMutationFunctionType } from "@/types/api";
import { FlowType } from "@/types/flow";
import { processFlows } from "@/utils/reactflowUtils";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetFlow {
  id: string;
}

// add types for error handling and success
export const useGetFlow: useMutationFunctionType<undefined, IGetFlow> = (
  options,
) => {
  const { mutate } = UseRequestProcessor();
  const queryClient = useQueryClient();

  const getFlowFn = async (payload: IGetFlow): Promise<FlowType> => {
    const response = await api.get<FlowType>(
      `${getURL("FLOWS")}/${payload.id}`,
    );

    const flowsArrayToProcess = [response.data];
    const { flows } = processFlows(flowsArrayToProcess);
    return flows[0];
  };

  const mutation = mutate(["useGetFlow"], getFlowFn, {
    ...options,
    onSettled: (response) => {
      if (response) {
        queryClient.refetchQueries({
          queryKey: [
            "useGetRefreshFlowsQuery",
            { get_all: true, header_flows: true },
          ],
        });
      }
    },
  });

  return mutation;
};
