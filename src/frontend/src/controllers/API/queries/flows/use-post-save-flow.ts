import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { ReactFlowJsonObject } from "reactflow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostSaveFlow {
  name: string;
  data: ReactFlowJsonObject;
  description: string;
  is_component: boolean;
  folder_id: string;
  endpoint_name: string;
}

export const usePostSaveFlow: useMutationFunctionType<
  undefined,
  IPostSaveFlow
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postSaveFlowFn = async (payload: IPostSaveFlow): Promise<any> => {
    const response = await api.post(`${getURL("FLOWS")}flows/`, {
      name: payload.name,
      data: payload.data,
      description: payload.description,
      is_component: payload.is_component,
      folder_id: payload.folder_id === "" ? null : payload.folder_id,
      endpoint_name: payload.endpoint_name,
    });

    return response.data;
  };

  const mutation: UseMutationResult<IPostSaveFlow, any, IPostSaveFlow> = mutate(
    ["usePostSaveFlow"],
    async (payload: IPostSaveFlow) => {
      const res = await postSaveFlowFn(payload);
      return res;
    },
    options,
  );

  return mutation;
};
