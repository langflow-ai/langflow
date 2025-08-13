import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteKnowledgeBaseParams {
  kb_name: string;
}

export const useDeleteKnowledgeBase: useMutationFunctionType<
  DeleteKnowledgeBaseParams,
  void
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteKnowledgeBaseFn = async (): Promise<any> => {
    const response = await api.delete<any>(
      `${getURL("KNOWLEDGE_BASES")}/${params.kb_name}`,
    );
    return response.data;
  };

  const mutation: UseMutationResult<any, any, void> = mutate(
    ["useDeleteKnowledgeBase"],
    deleteKnowledgeBaseFn,
    {
      onSettled: (data, error, variables, context) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetKnowledgeBases"],
        });
        options?.onSettled?.(data, error, variables, context);
      },
      ...options,
    },
  );

  return mutation;
};
