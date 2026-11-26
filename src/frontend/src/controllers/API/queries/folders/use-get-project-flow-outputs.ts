import type { FlowOutputChoice } from "@/pages/MainPage/entities";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetProjectFlowOutputsQuery: useQueryFunctionType<
  { projectId: string; fieldName: string },
  FlowOutputChoice[]
> = ({ projectId, fieldName }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["useGetProjectFlowOutputs", projectId, fieldName],
    async () => {
      const { data } = await api.get<FlowOutputChoice[]>(
        `${getURL("PROJECTS")}/${projectId}/flow-outputs`,
        { params: { field_name: fieldName } },
      );
      return data;
    },
    { enabled: !!projectId, ...options },
  );
};
