import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { DatasetInfo } from "./use-get-datasets";

interface CreateDatasetFromMessagesParams {
  name: string;
  description?: string;
  session_ids: string[];
  flow_id: string;
}

export const useCreateDatasetFromMessages: useMutationFunctionType<
  undefined,
  CreateDatasetFromMessagesParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createDatasetFromMessagesFn = async (
    params: CreateDatasetFromMessagesParams,
  ): Promise<DatasetInfo> => {
    const response = await api.post<DatasetInfo>(
      `${getURL("DATASETS")}/from-messages`,
      {
        name: params.name,
        description: params.description,
        session_ids: params.session_ids,
        flow_id: params.flow_id,
      },
    );
    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
    return response.data;
  };

  const mutation: UseMutationResult<
    DatasetInfo,
    any,
    CreateDatasetFromMessagesParams
  > = mutate(
    ["useCreateDatasetFromMessages"],
    createDatasetFromMessagesFn,
    options,
  );

  return mutation;
};
