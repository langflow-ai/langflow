import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

interface ComposerUrlResponse {
  project_id: string;
  sse_url: string;
  uses_composer: boolean;
}

async function getProjectComposerUrl(
  projectId: string,
): Promise<ComposerUrlResponse> {
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
    // Handle 400 error when project doesn't have OAuth auth
    // This allows the UI to gracefully fall back to direct SSE
    throwOnError: (error: any) => {
      // Don't throw on 400 errors (non-OAuth projects)
      return error?.status !== 400;
    },
  });
}
