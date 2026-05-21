import type {
  JobStatus,
  TriggerJob,
} from "@/pages/MainPage/pages/triggersPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetTriggerJobsParams {
  flowId: string;
  componentId: string;
  status?: JobStatus;
  limit?: number;
}

export const useGetTriggerJobs: useQueryFunctionType<
  GetTriggerJobsParams,
  TriggerJob[]
> = ({ flowId, componentId, status, limit = 50 }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<TriggerJob[]> => {
    const params: Record<string, unknown> = { limit };
    if (status) params.status_filter = status;
    const { data } = await api.get<TriggerJob[]>(
      `${getURL("TRIGGERS")}/${flowId}/${encodeURIComponent(componentId)}/jobs`,
      { params },
    );
    return data;
  };

  return query(
    ["useGetTriggerJobs", { flowId, componentId, status, limit }],
    fn,
    options,
  );
};
