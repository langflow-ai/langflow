import type { UseMutationResult } from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchUpdateFlow {
  id: string;
  name?: string;
  data?: ReactFlowJsonObject;
  description?: string;
  folder_id?: string | null | undefined;
  endpoint_name?: string | null | undefined;
  locked?: boolean | null | undefined;
  access_type?: "PUBLIC" | "PRIVATE" | "PROTECTED";
  mcp_enabled?: boolean | null;
  action_name?: string | null;
  action_description?: string | null;
  long_running?: boolean | null;
  default_timeout_s?: number | null;
}

export const usePatchUpdateFlow: useMutationFunctionType<
  undefined,
  IPatchUpdateFlow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const PatchUpdateFlowFn = async ({
    id,
    ...payload
    // biome-ignore lint/suspicious/noExplicitAny: pre-existing untyped response
  }: IPatchUpdateFlow): Promise<any> => {
    const response = await api.patch(`${getURL("FLOWS")}/${id}`, payload);

    return response.data;
  };

  // biome-ignore lint/suspicious/noExplicitAny: pre-existing untyped error
  const mutation: UseMutationResult<IPatchUpdateFlow, any, IPatchUpdateFlow> =
    mutate(["usePatchUpdateFlow"], PatchUpdateFlowFn, {
      onSettled: () => {
        queryClient.invalidateQueries({
          queryKey: ["useGetRefreshFlowsQuery"],
        });
        queryClient.invalidateQueries({
          queryKey: ["useGetFolders"],
        });
        queryClient.invalidateQueries({
          queryKey: ["useGetFolder"],
        });
      },
      ...options,
    });

  return mutation;
};
