import type { UseMutationResult } from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
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
  flow_activity_enabled?: boolean;
}

export const usePatchUpdateFlow: useMutationFunctionType<
  undefined,
  IPatchUpdateFlow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const PatchUpdateFlowFn = async ({
    id,
    ...payload
  }: IPatchUpdateFlow): Promise<FlowType> => {
    const response = await api.patch(`${getURL("FLOWS")}/${id}`, payload);

    return response.data;
  };

  const mutation: UseMutationResult<IPatchUpdateFlow, Error, IPatchUpdateFlow> =
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
