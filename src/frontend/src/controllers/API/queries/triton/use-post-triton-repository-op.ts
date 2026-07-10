import type { UseMutationResult } from "@tanstack/react-query";
import type {
  useMutationFunctionType,
  useQueryFunctionType,
} from "@/types/api";
import type { TritonRepositoryIndexEntry } from "@/types/triton";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type TritonRepositoryOp = "load" | "unload";

interface PostTritonRepositoryOpArgs {
  serverId: string;
  modelName: string;
  op: TritonRepositoryOp;
}

export const usePostTritonRepositoryOp: useMutationFunctionType<
  undefined,
  PostTritonRepositoryOpArgs,
  { detail: string }
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function runOp({
    serverId,
    modelName,
    op,
  }: PostTritonRepositoryOpArgs): Promise<{ detail: string }> {
    await api.post(
      `${getURL("TRITON_SERVERS")}/${serverId}/repository/models/${modelName}/${op}`,
      {},
    );
    return { detail: `${op} requested for ${modelName}` };
  }

  const mutation: UseMutationResult<
    { detail: string },
    Error,
    PostTritonRepositoryOpArgs
  > = mutate(["usePostTritonRepositoryOp"], runOp, {
    ...options,
    onSettled: (data, error, variables, context) => {
      const args = variables as unknown as PostTritonRepositoryOpArgs;
      const sid = args?.serverId;
      if (sid) {
        queryClient.refetchQueries({
          queryKey: ["useGetTritonRepositoryIndex", sid],
        });
        queryClient.refetchQueries({
          queryKey: ["useGetTritonModels", sid],
        });
      }
      options?.onSettled?.(data, error, variables, context);
    },
  });

  return mutation;
};

interface GetTritonRepositoryIndexParams {
  serverId: string;
}

export const useGetTritonRepositoryIndex: useQueryFunctionType<
  GetTritonRepositoryIndexParams,
  TritonRepositoryIndexEntry[]
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<TritonRepositoryIndexEntry[]> => {
    const { data } = await api.post<{
      models?: TritonRepositoryIndexEntry[];
    }>(`${getURL("TRITON_SERVERS")}/${params.serverId}/repository/index`, {});
    return data?.models ?? [];
  };

  return query(["useGetTritonRepositoryIndex", params.serverId], responseFn, {
    ...options,
    enabled: (options?.enabled ?? true) && Boolean(params.serverId),
  });
};
