import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type MCPJobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface MCPJob {
  id: string;
  project_id: string;
  flow_id: string;
  tool_name: string;
  status: MCPJobStatus;
  progress: number;
  result: Record<string, unknown> | null;
  error: string | null;
  callback_url: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface ListMCPJobsParams {
  project_id?: string;
  flow_id?: string;
  status?: MCPJobStatus;
  limit?: number;
  offset?: number;
}

function buildQueryString(params: ListMCPJobsParams): string {
  const entries: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    entries.push(
      `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`,
    );
  }
  return entries.length ? `?${entries.join("&")}` : "";
}

export function useListMCPJobs(params: ListMCPJobsParams = {}) {
  const { query } = UseRequestProcessor();
  return query(
    ["mcp-jobs", params],
    async (): Promise<MCPJob[]> => {
      const url = `${getURL("MCP_JOBS_BASE", undefined, true) ?? "/api/v1/mcp/jobs"}${buildQueryString(params)}`;
      const { data } = await api.get<MCPJob[]>(url);
      return data;
    },
    { refetchInterval: 5000 },
  );
}

export async function cancelMCPJob(jobId: string): Promise<MCPJob> {
  const baseUrl =
    getURL("MCP_JOBS_BASE", undefined, true) ?? "/api/v1/mcp/jobs";
  const { data } = await api.delete<MCPJob>(`${baseUrl}/${jobId}`);
  return data;
}
