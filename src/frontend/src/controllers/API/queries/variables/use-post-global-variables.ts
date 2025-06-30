import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { AxiosResponse } from "axios";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PostGlobalVariablesParams {
  name: string;
  value: string;
  type?: string;
  default_fields?: string[];
  category?: string;
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
    category,
  }): Promise<AxiosResponse<{ name: string; id: string; type: string }>> => {
    const res = await api.post(`${getURL("VARIABLES")}/`, {
      name,
      value,
      type,
      default_fields: default_fields,
      category,
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
