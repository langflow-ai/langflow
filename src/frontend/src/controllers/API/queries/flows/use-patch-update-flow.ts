import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { ReactFlowJsonObject } from "reactflow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchUpdateFlow {
  id: string;
  name: string;
  data: ReactFlowJsonObject;
  description: string;
  folder_id: string | null | undefined;
  endpoint_name: string | null | undefined;
}

export const usePatchUpdateFlow: useMutationFunctionType<
  undefined,
  IPatchUpdateFlow
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const PatchUpdateFlowFn = async (payload: IPatchUpdateFlow): Promise<any> => {
    if (payload.data.nodes.length === 0) return null;
    const response = await api.patch(`${getURL("FLOWS")}/${payload.id}`, {
      name: payload.name,
      data: payload.data,
      description: payload.description,
      folder_id: payload.folder_id || null,
      endpoint_name: payload.endpoint_name || null,
    });

    return response.data;
  };

  const mutation: UseMutationResult<IPatchUpdateFlow, any, IPatchUpdateFlow> =
    mutate(["usePatchUpdateFlow"], PatchUpdateFlowFn, options);

  return mutation;
};
