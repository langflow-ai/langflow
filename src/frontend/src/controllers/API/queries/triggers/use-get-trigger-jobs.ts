import type {
  JobStatus,
  TriggerJob,
} from "@/pages/MainPage/pages/triggersPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetTriggerJobsParams {
  triggerId: string;
  status?: JobStatus;
  limit?: number;
}

export const useGetTriggerJobs: useQueryFunctionType<
  GetTriggerJobsParams,
  TriggerJob[]
> = ({ triggerId, status, limit = 50 }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<TriggerJob[]> => {
    const params: Record<string, unknown> = { limit };
    if (status) params.status_filter = status;
    const { data } = await api.get<TriggerJob[]>(
      `${getURL("TRIGGERS")}/${triggerId}/jobs`,
      { params },
    );
    return data;
  };

  return query(
    ["useGetTriggerJobs", { triggerId, status, limit }],
    fn,
    options,
  );
};
