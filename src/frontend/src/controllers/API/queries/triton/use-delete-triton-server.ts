import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteTritonServerArgs {
  server_id: string;
}

interface DeleteTritonServerResponse {
  detail?: string;
}

export const useDeleteTritonServer: useMutationFunctionType<
  undefined,
  DeleteTritonServerArgs,
  DeleteTritonServerResponse
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function deleteServer({
    server_id,
  }: DeleteTritonServerArgs): Promise<DeleteTritonServerResponse> {
    try {
      const res = await api.delete(`${getURL("TRITON_SERVERS")}/${server_id}`);
      return { detail: res.data?.detail ?? "Triton server deleted" };
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to delete Triton server",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    DeleteTritonServerResponse,
    Error,
    DeleteTritonServerArgs
  > = mutate(["useDeleteTritonServer"], deleteServer, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.refetchQueries({ queryKey: ["useGetTritonServers"] });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
