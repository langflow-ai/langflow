import { keepPreviousData } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { WORKFLOWS_ENDPOINT } from "../../agui/run-agent";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface PendingHumanRequest {
  job_id: string;
  flow_id: string;
  session_id: string | null;
  created_at: string | null;
  request_id: string;
  kind: string | null;
  prompt: string | null;
  options: { action_id: string; label?: string }[];
  allowed_decisions: string[];
}

/**
 * Suspended human-in-the-loop runs for a flow plus their pending request.
 *
 * Backs the Traces overlay: paused jobs live in a separate store from traces, so the
 * UI correlates these to trace rows by session_id and surfaces the resume action.
 */
export const useGetPendingWorkflows: useQueryFunctionType<
  { flowId?: string },
  PendingHumanRequest[]
> = ({ flowId }, options) => {
  const { query } = UseRequestProcessor();

  const getPendingFn = async (): Promise<PendingHumanRequest[]> => {
    if (!flowId) return [];
    const result = await api.get<PendingHumanRequest[]>(
      `${WORKFLOWS_ENDPOINT}/pending`,
      { params: { flow_id: flowId } },
    );
    return result.data;
  };

  return query(["useGetPendingWorkflows", flowId], getPendingFn, {
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
    refetchInterval: 5000,
    ...options,
  });
};
