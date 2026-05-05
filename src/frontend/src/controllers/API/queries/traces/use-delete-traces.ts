import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteTracesMutation: useMutationFunctionType<
  undefined,
  { flow_id: string }
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const deleteTracesFn = async (params: {
    flow_id: string;
  }): Promise<undefined> => {
    await api.delete(`${getURL("TRACES")}`, { params });
    return undefined;
  };

  return mutate(["useDeleteTracesMutation"], deleteTracesFn, options);
};
