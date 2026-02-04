import type { UseMutationResult } from '@tanstack/react-query';
import type { useMutationFunctionType } from '@/types/api';
import { api } from '../../api';
import { getURL } from '../../helpers/constants';
import { UseRequestProcessor } from '../../services/request-processor';

export interface AddSourceRequest {
  kb_name: string;
  source_name: string;
  file_ids: string[];
}

export interface AddSourceResponse {
  message: string;
  documents_added: number;
  source_name: string;
}

export const useAddSourceToKnowledgeBase: useMutationFunctionType<
  undefined,
  AddSourceRequest,
  AddSourceResponse
> = options => {
  const { mutate, queryClient } = UseRequestProcessor();

  const addSourceFn = async (
    payload: AddSourceRequest
  ): Promise<AddSourceResponse> => {
    const { kb_name, source_name, file_ids } = payload;
    const res = await api.post<AddSourceResponse>(
      `${getURL('KNOWLEDGE_BASES')}/${kb_name}/sources`,
      {
        source_name,
        files: file_ids,
      }
    );
    return res.data;
  };

  const mutation: UseMutationResult<AddSourceResponse, any, AddSourceRequest> =
    mutate(['useAddSourceToKnowledgeBase'], addSourceFn, {
      onSettled: (data, error, variables, context) => {
        queryClient.invalidateQueries({
          queryKey: ['useGetKnowledgeBases'],
        });
        options?.onSettled?.(data, error, variables, context);
      },
      ...options,
    });

  return mutation;
};
