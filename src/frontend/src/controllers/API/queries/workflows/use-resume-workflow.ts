import type { useMutationFunctionType } from "@/types/api";
import { WORKFLOWS_ENDPOINT } from "../../agui/run-agent";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ResumeWorkflowPayload {
  jobId: string;
  requestId: string;
  decision: { action_id: string; values: Record<string, string> };
}

export interface ResumeWorkflowResponse {
  job_id: string;
  status: string;
  message?: string;
}

/**
 * Resume a SUSPENDED human-in-the-loop run with the human's decision.
 *
 * POSTs the decision to `/api/v2/workflows/{job_id}/resume` (LE-1450). The caller
 * re-attaches a fresh `GET /{job_id}/events` from the last seen event id so the
 * continued run streams gap-free.
 */
export const useResumeWorkflow: useMutationFunctionType<
  undefined,
  ResumeWorkflowPayload,
  ResumeWorkflowResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const resumeFn = async (
    payload: ResumeWorkflowPayload,
  ): Promise<ResumeWorkflowResponse> => {
    const res = await api.post(
      `${WORKFLOWS_ENDPOINT}/${encodeURIComponent(payload.jobId)}/resume`,
      { request_id: payload.requestId, decision: payload.decision },
    );
    return res.data;
  };

  return mutate(["useResumeWorkflow"], resumeFn, options);
};
