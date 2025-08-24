import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

interface ComposerUrlResponse {
  project_id: string;
  composer_port: number;
  composer_host: string;
  composer_sse_url: string;
}

async function getProjectComposerUrl(projectId: string): Promise<ComposerUrlResponse> {
  const response = await api.get(`${getURL("MCP")}/${projectId}/composer-url`);
  return response.data;
}

export function useGetProjectComposerUrl(projectId: string) {
  return useQuery({
    queryKey: ["project-composer-url", projectId],
    queryFn: () => getProjectComposerUrl(projectId),
    enabled: !!projectId,
    staleTime: 30000, // 30 seconds
    retry: 1,
  });
}