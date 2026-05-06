import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface LocalModelStatus {
  is_docker: boolean;
  is_ollama_installed: boolean;
  is_ollama_running: boolean;
  is_model_pulled: boolean;
  default_model: string;
  ready: boolean;
}

export const useGetLocalModelStatus: useQueryFunctionType<
  undefined,
  LocalModelStatus
> = (_params, options) => {
  const { query } = UseRequestProcessor();

  const getLocalModelStatusFn = async (): Promise<LocalModelStatus> => {
    const response = await api.get<LocalModelStatus>(
      `${getURL("LOCAL_MODEL")}/status`,
    );
    return response.data;
  };

  return query(["useGetLocalModelStatus"], getLocalModelStatusFn, {
    refetchOnWindowFocus: false,
    staleTime: 1000 * 30,
    ...options,
  });
};
