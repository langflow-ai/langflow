import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface IApiKeysDataArray {
  name: string;
  last_used_at: string | null;
  total_uses: number;
  is_active: boolean;
  id: string;
  api_key: string;
  user_id: string;
  created_at: string;
}

interface IApiQueryResponse {
  total_count: number;
  user_id: string;
  api_keys: Array<IApiKeysDataArray>;
}

export const useGetApiKeysQuery: useQueryFunctionType<
  undefined,
  IApiQueryResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getApiKeysFn = async () => {
    return await api.get<IApiQueryResponse>(`${getURL("API_KEY")}/`);
  };

  const responseFn = async () => {
    const { data } = await getApiKeysFn();
    return data;
  };

  const queryResult = query(["useGetApiKeysQuery"], responseFn, { ...options });

  return queryResult;
};
