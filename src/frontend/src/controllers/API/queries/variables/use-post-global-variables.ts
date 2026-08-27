import type { UseMutationResult } from "@tanstack/react-query";
import { VALID_CATEGORIES } from "@/constants/constants";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  appendProviderScope,
  type ProviderScopeParams,
} from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";
import { getGlobalVariablesQueryKey } from "./use-get-global-variables";

type VariableCategory = (typeof VALID_CATEGORIES)[number];

interface PostGlobalVariablesParams extends ProviderScopeParams {
  name: string;
  value: string;
  type?: string;
  default_fields?: string[];
  category?: VariableCategory;
}

interface PostGlobalVariablesResponse {
  name: string;
  id: string;
  type: string;
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
    flowId,
    projectId,
  }: PostGlobalVariablesParams): Promise<PostGlobalVariablesResponse> => {
    const queryParams = new URLSearchParams();
    appendProviderScope(queryParams, { flowId, projectId });
    const res = await api.post(
      `${getURL("VARIABLES")}/${
        queryParams.toString() ? `?${queryParams.toString()}` : ""
      }`,
      {
        name,
        value,
        type,
        default_fields: default_fields,
        category,
      },
    );
    return res.data;
  };

  const mutation: UseMutationResult<
    PostGlobalVariablesResponse,
    unknown,
    PostGlobalVariablesParams
  > = mutate(["usePostGlobalVariables"], postGlobalVariablesFunction, {
    onSettled: (data, error, variables) => {
      queryClient.refetchQueries({
        queryKey: getGlobalVariablesQueryKey(variables),
        exact: true,
      });
      if (variables.category) {
        queryClient.refetchQueries({
          queryKey: ["category-variable", variables.category],
        });
      }
    },
    retry: false,
    ...options,
  });

  return mutation;
};
