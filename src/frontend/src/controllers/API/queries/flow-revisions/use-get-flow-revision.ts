import type { useQueryFunctionType } from "@/types/api";
import type { RevisionGraph } from "@/types/flow/revision";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowRevisionParams {
  flowId: string;
  revision: number | null;
}

export const getFlowRevision = async (
  flowId: string,
  revision: number,
): Promise<RevisionGraph> => {
  const response = await api.get<RevisionGraph>(
    `${getURL("FLOWS")}/${flowId}/revisions/${revision}`,
  );
  return response.data;
};

/** Whether a request failed because compaction removed the revision it asked for. */
export const isRevisionNotRetained = (error: unknown): boolean => {
  const response = (
    error as {
      response?: { status?: number; data?: { detail?: { code?: string } } };
    } | null
  )?.response;
  return (
    response?.status === 410 &&
    response.data?.detail?.code === "FLOW_REVISION_NOT_RETAINED"
  );
};

/** The flow's graph at one revision, with literal secrets removed. */
export const useGetFlowRevision: useQueryFunctionType<
  FlowRevisionParams,
  RevisionGraph
> = ({ flowId, revision }, options) => {
  const { query } = UseRequestProcessor();

  return query(
    ["useGetFlowRevision", { flowId, revision }],
    () => getFlowRevision(flowId, revision as number),
    {
      ...options,
      enabled: revision !== null && (options?.enabled ?? true),
    },
  );
};
