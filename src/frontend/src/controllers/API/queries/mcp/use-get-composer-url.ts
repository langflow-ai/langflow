import type { useQueryFunctionType } from "@/types/api";
import type { ComposerUrlResponseType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type UseGetProjectComposerUrlParams = {
  projectId: string;
};

export const useGetProjectComposerUrl: useQueryFunctionType<
  UseGetProjectComposerUrlParams,
  ComposerUrlResponseType
> = ({ projectId }, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<ComposerUrlResponseType> => {
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
