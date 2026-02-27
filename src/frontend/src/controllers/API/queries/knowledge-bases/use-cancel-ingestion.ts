import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface CancelIngestionParams {
  kb_name: string;
}

export const useCancelIngestion: useMutationFunctionType<
  undefined,
  CancelIngestionParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const cancelIngestionFn = async (
    params: CancelIngestionParams,
  ): Promise<any> => {
    const response = await api.post<any>(
      `${getURL("KNOWLEDGE_BASES")}/${params.kb_name}/cancel`,
    );
    return response.data;
  };

  const mutation: UseMutationResult<any, any, CancelIngestionParams> = mutate(
    ["useCancelIngestion"],
    cancelIngestionFn,
    {
      onSettled: (data, error, variables, context, ...rest) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetKnowledgeBases"],
        });
        options?.onSettled?.(data, error, variables, context, ...rest);
      },
      ...options,
    },
  );

  return mutation;
};
