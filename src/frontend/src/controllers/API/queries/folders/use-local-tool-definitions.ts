import type { LocalToolBinding } from "@/pages/MainPage/entities";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useLocalToolDefinitions: useQueryFunctionType<
  { projectId: string },
  LocalToolBinding[]
> = ({ projectId }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["localToolDefinitions", projectId],
    async () => {
      const { data } = await api.get<LocalToolBinding[]>(
        `${getURL("PROJECTS")}/${projectId}/tool-definitions`,
      );
      return data;
    },
    { enabled: !!projectId, ...options },
  );
};
