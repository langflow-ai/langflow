import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type ReportExecution = {
  flow_id: string;
  run_id: string;
  node_id: string;
};

export type ReportSummary = {
  id: string;
  title: string;
  created_at: string;
  execution: ReportExecution;
  source_count: number;
  citation_count: number;
  unresolved_citation_count: number;
  citations_resolved: boolean;
  claim_support: "not_evaluated";
};

export type ReportSource = {
  id: string;
  title: string;
  uri: string;
  content: string;
  captured_at: string;
  availability: "available" | "unavailable";
  unavailable_reason: string;
};

export type SourcedReport = {
  schema_version: 1;
  id: string;
  title: string;
  markdown: string;
  created_at: string;
  execution: ReportExecution;
  sources: ReportSource[];
  source_uses: {
    source_id: string;
    tool_call_id: string;
    tool_name: string | null;
  }[];
  claim_support: "not_evaluated";
};

type ReportPage = {
  items: ReportSummary[];
  next_cursor: string | null;
  unavailable_count: number;
};

type ReportReference = { projectId: string; flowId: string; reportId: string };

const reportsURL = (projectId: string) =>
  `${getURL("PROJECTS")}/${encodeURIComponent(projectId)}/reports`;
const reportURL = ({ projectId, flowId, reportId }: ReportReference) =>
  `${reportsURL(projectId)}/${encodeURIComponent(flowId)}/${encodeURIComponent(reportId)}`;

export const useProjectReports: useQueryFunctionType<
  { projectId: string; cursor?: string },
  ReportPage
> = ({ projectId, cursor }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["projectReports", projectId, cursor],
    async ({ signal }) =>
      (
        await api.get<ReportPage>(reportsURL(projectId), {
          params: { limit: 20, cursor },
          signal,
        })
      ).data,
    { retry: false, ...options },
  );
};

export const useProjectReport: useQueryFunctionType<
  ReportReference,
  SourcedReport
> = (reference, options) => {
  const { query } = UseRequestProcessor();
  return query(
    [
      "projectReport",
      reference.projectId,
      reference.flowId,
      reference.reportId,
    ],
    async ({ signal }) =>
      (await api.get<SourcedReport>(reportURL(reference), { signal })).data,
    { retry: false, gcTime: 0, ...options },
  );
};

export async function downloadProjectReport(
  reference: ReportReference,
  format: "markdown" | "json",
) {
  const { data } = await api.get<Blob>(
    `${reportURL(reference)}/download/${format}`,
    {
      responseType: "blob",
    },
  );
  const url = URL.createObjectURL(data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `report-${reference.reportId}.${format === "markdown" ? "md" : "json"}`;
  anchor.click();
  // Let the browser begin consuming the blob before releasing it.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
