import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export type GroupItem = {
  session_id: string;
  count: number;
  trace_ids: string[];
};

export type GroupedTracesResponse = {
  timeframe?: string;
  search_name?: string;
  groups: GroupItem[];
};

export async function getTracesBySessionGrouped(params: {
  name: string;
  timeframe?: string;
}): Promise<GroupedTracesResponse> {
  const url = `${getURL("OBSERVABILITY")}/get-traces/by-session-grouped`;
  const res = await api.get<GroupedTracesResponse>(url, { params });
  return res.data;
}

export async function getSessionSummary(session_id: string): Promise<any> {
  const url = `${getURL("OBSERVABILITY")}/sessions/${encodeURIComponent(session_id)}/summary`;
  const res = await api.get(url);
  return res.data;
}

export async function getLatestSessionSummary(session_id: string): Promise<any> {
  const url = `${getURL("OBSERVABILITY")}/sessions/${encodeURIComponent(session_id)}/latest-summary`;
  const res = await api.get(url);
  return res.data;
}

export async function getTraces(trace_id: string): Promise<any> {
  const url = `${getURL("OBSERVABILITY")}/traces/${trace_id}?include_observations=true`;
  const res = await api.get(url);
  return res.data;    
}   