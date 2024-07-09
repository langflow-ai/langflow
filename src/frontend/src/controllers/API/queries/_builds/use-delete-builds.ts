import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFLowPool {
  flowId: string;
}

// add types for error handling and success
export const useDeleteFLowPool: useMutationFunctionType<IDeleteFLowPool> = (
  options,
) => {
  const { mutate } = UseRequestProcessor();

  const deleteFLowPoolFn = async (payload: IDeleteFLowPool): Promise<any> => {
    const config = {};
    config["params"] = { flow_id: payload.flowId };
    const res = await api.delete<any>(`${getURL("BUILDS")}`, config);
    return res.data;
  };

  const mutation = mutate(["useDeleteFLowPool"], deleteFLowPoolFn, options);

  return mutation;
};
