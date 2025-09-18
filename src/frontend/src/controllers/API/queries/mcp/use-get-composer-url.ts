import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ComposerUrlResponse {
  project_id: string;
  sse_url: string;
  uses_composer: boolean;
  error_message?: string;
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
    // Backend returns 200 responses with error_message field instead of HTTP errors
    ...options,
  });
};
