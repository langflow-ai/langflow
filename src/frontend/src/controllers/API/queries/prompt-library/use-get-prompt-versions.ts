import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { ApiResponse, VersionsListResponse } from "./types";

export const useGetPromptVersions = (promptId: string | undefined, enabled = true) => {
  const url = `${getURL("PROMPT_LIBRARY")}/prompts/${promptId}/versions`;

  return useQuery({
    queryKey: ["useGetPromptVersions", promptId],
    queryFn: async () => {
      const response = await api.get<ApiResponse<VersionsListResponse>>(url);
      return response.data.data;
    },
    enabled: !!promptId && enabled,
  });
};
