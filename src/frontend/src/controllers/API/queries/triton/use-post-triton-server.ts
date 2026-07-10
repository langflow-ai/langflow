import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { TritonServerCreateType, TritonServerType } from "@/types/triton";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

export const usePostTritonServer: useMutationFunctionType<
  undefined,
  TritonServerCreateType,
  TritonServerType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function createServer(
    payload: TritonServerCreateType,
  ): Promise<TritonServerType> {
    try {
      const { data } = await api.post<TritonServerType>(
        `${getURL("TRITON_SERVERS")}/`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to add Triton server",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    TritonServerType,
    Error,
    TritonServerCreateType
  > = mutate(["usePostTritonServer"], createServer, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.refetchQueries({ queryKey: ["useGetTritonServers"] });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
