import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteKnowledgeBases {
  kb_names: string[];
}

export const useDeleteKnowledgeBases: useMutationFunctionType<
  undefined,
  IDeleteKnowledgeBases
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteKnowledgeBasesFn = async (
    params: IDeleteKnowledgeBases,
  ): Promise<any> => {
    const response = await api.delete<any>(`${getURL("KNOWLEDGE_BASES")}/`, {
      data: { kb_names: params.kb_names },
    });

    return response.data;
  };

  const mutation: UseMutationResult<any, any, IDeleteKnowledgeBases> = mutate(
    ["useDeleteKnowledgeBases"],
    deleteKnowledgeBasesFn,
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
