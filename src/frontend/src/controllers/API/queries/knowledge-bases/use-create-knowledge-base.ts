import type { UseMutationResult } from '@tanstack/react-query';
import type { useMutationFunctionType } from '@/types/api';
import { api } from '../../api';
import { getURL } from '../../helpers/constants';
import { UseRequestProcessor } from '../../services/request-processor';
import type { KnowledgeBaseInfo } from './use-get-knowledge-bases';

export interface CreateKnowledgeBaseRequest {
  name: string;
  embedding_provider: string;
  embedding_model: string;
}

export const useCreateKnowledgeBase: useMutationFunctionType<
  undefined,
  CreateKnowledgeBaseRequest,
  KnowledgeBaseInfo
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createKnowledgeBaseFn = async (
    payload: CreateKnowledgeBaseRequest
  ): Promise<KnowledgeBaseInfo> => {
    const res = await api.post<KnowledgeBaseInfo>(
      `${getURL('KNOWLEDGE_BASES')}/`,
      payload
    );
    return res.data;
  };

  const mutation: UseMutationResult<
    KnowledgeBaseInfo,
    any,
    CreateKnowledgeBaseRequest
  > = mutate(['useCreateKnowledgeBase'], createKnowledgeBaseFn, {
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
