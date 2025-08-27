import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ComposerUrlResponse {
  project_id: string;
  sse_url: string;
  uses_composer: boolean;
  port_available: boolean;
}

type UseGetProjectComposerUrlParams = {
  projectId: string;
};

export const useGetProjectComposerUrl: useQueryFunctionType<
  UseGetProjectComposerUrlParams,
  ComposerUrlResponse
> = ({ projectId }, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<ComposerUrlResponse> => {
    try {
      const response = await api.get(
        `${getURL("MCP")}/${projectId}/composer-url`,
      );
      return response.data;
    } catch (error) {
      console.error(error);
      throw error;
    }
  };

  return query(["project-composer-url", projectId], responseFn, {
    staleTime: 30000, // 30 seconds
    retry: 1,
    // Handle 400/500 errors when project doesn't have OAuth auth
    // This allows the UI to gracefully fall back to direct SSE
    throwOnError: (error: unknown) => {
      // Don't throw on 400 errors (non-OAuth projects) or 500 errors (auth transition states)
      const errorWithStatus = error as { status?: number };
      return errorWithStatus?.status !== 400 && errorWithStatus?.status !== 500;
    },
    ...options,
  });
};
