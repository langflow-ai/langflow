import type { useQueryFunctionType } from "@/types/api";
import type { FlowVersionEntryWithData } from "@/types/flow/version";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowVersionEntryParams {
  flowId: string;
  versionId: string;
}

export const getFlowVersionEntry = async ({
  flowId,
  versionId,
}: FlowVersionEntryParams): Promise<FlowVersionEntryWithData> => {
  const response = await api.get<FlowVersionEntryWithData>(
    `${getURL("FLOWS")}/${flowId}/versions/${versionId}`,
  );
  return response.data;
};

export const useGetFlowVersionEntry: useQueryFunctionType<
  FlowVersionEntryParams,
  FlowVersionEntryWithData
> = ({ flowId, versionId }, options) => {
  const { query } = UseRequestProcessor();

  return query(
    ["useGetFlowVersionEntry", { flowId, versionId }],
    () => getFlowVersionEntry({ flowId, versionId }),
    {
      ...options,
      enabled: !!versionId && (options?.enabled ?? true),
    },
  );
};
