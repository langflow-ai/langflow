import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { TritonServerType, TritonServerUpdateType } from "@/types/triton";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchTritonServerArgs {
  server_id: string;
  payload: TritonServerUpdateType;
}

export const usePatchTritonServer: useMutationFunctionType<
  undefined,
  PatchTritonServerArgs,
  TritonServerType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchServer({
    server_id,
    payload,
  }: PatchTritonServerArgs): Promise<TritonServerType> {
    try {
      const { data } = await api.patch<TritonServerType>(
        `${getURL("TRITON_SERVERS")}/${server_id}`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to update Triton server",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    TritonServerType,
    Error,
    PatchTritonServerArgs
  > = mutate(["usePatchTritonServer"], patchServer, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.refetchQueries({ queryKey: ["useGetTritonServers"] });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
