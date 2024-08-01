import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { ReactFlowJsonObject } from "reactflow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchUpdateFlow {
  name: string;
  data: ReactFlowJsonObject;
  description: string;
  folder_id: string;
  endpoint_name: string;
}

interface IPatchUpdateFlowParams {
  id: string;
}

export const usePatchUpdateFlow: useMutationFunctionType<
  IPatchUpdateFlowParams,
  IPatchUpdateFlow
> = (params, options?) => {
  const { mutate } = UseRequestProcessor();

  const PatchUpdateFlowFn = async (payload: IPatchUpdateFlow): Promise<any> => {
    const response = await api.patch(`${getURL("FLOWS")}/${params}`, {
      name: payload.name,
      data: payload.data,
      description: payload.description,
      folder_id: payload.folder_id === "" ? null : payload.folder_id,
      endpoint_name: payload.endpoint_name,
    });

    return response.data;
  };

  const mutation: UseMutationResult<IPatchUpdateFlow, any, IPatchUpdateFlow> =
    mutate(
      ["usePatchUpdateFlow", { id: params.id }],
      async (payload: IPatchUpdateFlow) => {
        const res = await PatchUpdateFlowFn(payload);
        return res;
      },
      options,
    );

  return mutation;
};
