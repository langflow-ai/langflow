import type { useMutationFunctionType } from "@/types/api";
import type { UseMutationResult } from "@tanstack/react-query";
import type { AxiosResponse } from "axios";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PostGlobalVariablesParams {
  name: string;
  value: string;
  type?: string;
  default_fields?: string[];
}

export const usePostGlobalVariables: useMutationFunctionType<
  undefined,
  PostGlobalVariablesParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postGlobalVariablesFunction = async ({
    name,
    value,
    type,
    default_fields = [],
  }): Promise<AxiosResponse<{ name: string; id: string; type: string }>> => {
    const res = await api.post(`${getURL("VARIABLES")}/`, {
      name,
      value,
      type,
      default_fields: default_fields,
    });
    return res.data;
  };

  const mutation: UseMutationResult<any, any, PostGlobalVariablesParams> =
    mutate(["usePostGlobalVariables"], postGlobalVariablesFunction, {
      onSettled: () => {
        queryClient.refetchQueries({ queryKey: ["useGetGlobalVariables"] });
      },
      ...options,
    });

  return mutation;
};
