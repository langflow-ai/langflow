import type { SnapshotUpdateResponse } from "@/pages/MainPage/pages/deploymentsPage/types";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface PatchSnapshotRequest {
  providerSnapshotId: string;
  flowVersionId: string;
}

export const usePatchSnapshot: useMutationFunctionType<
  undefined,
  PatchSnapshotRequest,
  SnapshotUpdateResponse
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async (
    payload: PatchSnapshotRequest,
  ): Promise<SnapshotUpdateResponse> => {
    const { data } = await api.patch<SnapshotUpdateResponse>(
      `${getURL("DEPLOYMENTS")}/snapshots/${payload.providerSnapshotId}`,
      { flow_version_id: payload.flowVersionId },
    );
    return data;
  };

  // TODO: Add retries for transient server-side errors (5xx, timeouts).
  return mutate(["usePatchSnapshot"], fn, {
    ...options,
    retry: false,
    onSuccess: (...args) => {
      queryClient.refetchQueries({ queryKey: ["useGetDeployments"] });
      options?.onSuccess?.(...args);
    },
  });
};
