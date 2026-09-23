import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type ToolPackReference = {
  project_id: string;
  expected_type: "tool-pack";
  revision: string;
};

export type FlowDependency = {
  flow_id: string;
  name: string;
  description?: string;
  revision: string;
};

export type ToolExport = FlowDependency & {
  description: string;
  dependencies?: FlowDependency[];
};

export type ToolPackManifest = {
  reference: ToolPackReference;
  name: string;
  tools: ToolExport[];
};

export type ToolPackBinding = {
  reference: ToolPackReference;
  tool: ToolExport;
  version_id: string;
  dependency_versions?: { flow: FlowDependency; version_id: string }[];
};

export type ToolDependencyUse = {
  tool_call_id: string;
  tool_name: string;
  binding: ToolPackBinding;
};

export const useProjectToolPack: useQueryFunctionType<
  { projectId: string },
  ToolPackManifest
> = ({ projectId }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["projectToolPack", projectId],
    async ({ signal }) =>
      (
        await api.get<ToolPackManifest>(
          `${getURL("PROJECTS")}/${encodeURIComponent(projectId)}/tool-pack`,
          { signal },
        )
      ).data,
    { retry: false, staleTime: 0, refetchOnWindowFocus: true, ...options },
  );
};
