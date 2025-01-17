import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface IStarterProjectsDataArray {
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
  api_keys: Array<IStarterProjectsDataArray>;
}

export const useGetStarterProjectsQuery: useQueryFunctionType<
  undefined,
  IApiQueryResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getStarterProjectsFn = async () => {
    return await api.get<IApiQueryResponse>(`${getURL("STARTER_PROJECTS")}/`);
  };

  const responseFn = async () => {
    const { data } = await getStarterProjectsFn();
    return data;
  };

  const queryResult = query(["useGetStarterProjectsQuery"], responseFn, {
    ...options,
  });

  return queryResult;
};
