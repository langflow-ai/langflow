import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { JsonPatchResponse } from "@/types/api/json-patch";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type PatchOperationType =
  | "add"
  | "remove"
  | "replace"
  | "move"
  | "copy"
  | "test";

export interface PatchOperation {
  op: PatchOperationType;
  path: string;
  value?: any;
  from?: string;
}

export interface JsonPatch {
  operations: PatchOperation[];
}

interface IPatchJsonPatchFlow {
  id: string;
  operations: PatchOperation[];
}

export const usePatchJsonPatchFlow: useMutationFunctionType<
  undefined,
  IPatchJsonPatchFlow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const PatchJsonPatchFlowFn = async ({
    id,
    operations,
  }: IPatchJsonPatchFlow): Promise<JsonPatchResponse> => {
    const response = await api.patch(`${getURL("FLOWS")}/${id}/json-patch`, {
      operations,
    });

    return response.data;
  };

  const mutation: UseMutationResult<
    JsonPatchResponse,
    any,
    IPatchJsonPatchFlow
  > = mutate(["usePatchJsonPatchFlow"], PatchJsonPatchFlowFn, {
    onSettled: (res) => {
      queryClient.refetchQueries({
        queryKey: ["useGetFolders", res?.folder_id],
      }),
        queryClient.refetchQueries({
          queryKey: ["useGetFolder"],
        });
    },
    ...options,
  });

  return mutation;
};
