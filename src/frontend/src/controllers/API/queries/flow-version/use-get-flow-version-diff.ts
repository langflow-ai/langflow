import type { useQueryFunctionType } from "@/types/api";
import type { FlowVersionDiff } from "@/types/flow/version";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowVersionDiffParams {
  flowId: string;
  versionId: string;
  /** A version id to compare against, or "draft" for the live flow. */
  against: string;
}

export const getFlowVersionDiff = async ({
  flowId,
  versionId,
  against,
}: FlowVersionDiffParams): Promise<FlowVersionDiff> => {
  const response = await api.get<FlowVersionDiff>(
    `${getURL("FLOWS")}/${flowId}/versions/${versionId}/diff`,
    { params: { against } },
  );
  return response.data;
};

export const useGetFlowVersionDiff: useQueryFunctionType<
  FlowVersionDiffParams,
  FlowVersionDiff
> = ({ flowId, versionId, against }, options) => {
  const { query } = UseRequestProcessor();

  return query(
    ["useGetFlowVersionDiff", { flowId, versionId, against }],
    () => getFlowVersionDiff({ flowId, versionId, against }),
    {
      ...options,
      enabled: !!versionId && !!against && (options?.enabled ?? true),
    },
  );
};
