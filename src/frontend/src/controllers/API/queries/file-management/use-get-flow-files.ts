import { keepPreviousData } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useQueryFunctionType } from "@/types/api";
import { api } from '@/controllers/API/api'
import { UseRequestProcessor } from "../../services/request-processor";

export interface FlowFileInfo {
  flow_id: string;
  flow_name: string;
  file_name: string;
  file_size: number;
}

export type FlowFilesResponse = FlowFileInfo[];

export const useGetFlowFiles: useQueryFunctionType<
  undefined,
  FlowFilesResponse
> = (config) => {
  const { query } = UseRequestProcessor();

  const getFlowFilesFn = async () => {
    const response = await api.get<FlowFilesResponse>(
      `${BASE_URL_API}files/list`,
    );
    return response["data"] ?? [];
  };

  const queryResult = query(["useGetFlowFiles"], getFlowFilesFn, {
    placeholderData: keepPreviousData,
    ...config,
  });

  return queryResult;
};
