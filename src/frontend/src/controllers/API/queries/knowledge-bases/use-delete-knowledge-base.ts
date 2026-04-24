import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteKnowledgeBaseParams {
  /** Single KB name or array of KB names for bulk delete */
  kb_names: string | string[];
}

export const useDeleteKnowledgeBase: useMutationFunctionType<
  undefined,
  DeleteKnowledgeBaseParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteKnowledgeBaseFn = async (
    params: DeleteKnowledgeBaseParams,
  ): Promise<any> => {
    const names = Array.isArray(params.kb_names)
      ? params.kb_names
      : [params.kb_names];

    // Use bulk endpoint for all deletes (works for single or multiple)
    const response = await api.delete<any>(`${getURL("KNOWLEDGE_BASES")}/`, {
      data: { kb_names: names },
    });
    return response.data;
  };

  const mutation: UseMutationResult<any, any, DeleteKnowledgeBaseParams> =
    mutate(["useDeleteKnowledgeBase"], deleteKnowledgeBaseFn, {
      onSettled: (data, error, variables, context, ...rest) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetKnowledgeBases"],
        });
        options?.onSettled?.(data, error, variables, context, ...rest);
      },
      ...options,
    });

  return mutation;
};
