import { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ConfigResponse {
  frontend_timeout: number;
  auto_saving: boolean;
}

export const useGetConfigQuery: useQueryFunctionType<
  undefined,
  ConfigResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getConfigFn = async () => {
    const response = await api.get<ConfigResponse>(`${getURL("CONFIG")}`);
    return response["data"];
  };

  const queryResult = query(["useGetConfigQuery"], getConfigFn, options);

  return queryResult;
};
