import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface SnapshotUpdateRequest {
  provider_snapshot_id: string;
  flow_version_id: string;
}

export interface SnapshotUpdateResponse {
  flow_version_id: string;
  provider_snapshot_id: string;
}

export const usePatchDeploymentSnapshot: useMutationFunctionType<
  undefined,
  SnapshotUpdateRequest,
  SnapshotUpdateResponse
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async (
    payload: SnapshotUpdateRequest,
  ): Promise<SnapshotUpdateResponse> => {
    const { provider_snapshot_id, flow_version_id } = payload;
    const res = await api.patch<SnapshotUpdateResponse>(
      `${getURL("DEPLOYMENTS")}/snapshots/${provider_snapshot_id}`,
      { flow_version_id },
    );
    return res.data;
  };

  return mutate(["usePatchDeploymentSnapshot"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.removeQueries({
        queryKey: ["useGetDeploymentAttachments"],
      });
      options?.onSuccess?.(...args);
    },
  });
};
