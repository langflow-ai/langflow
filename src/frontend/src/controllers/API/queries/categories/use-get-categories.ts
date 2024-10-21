import { useQueryFunctionType } from "@/types/api";
import { SidebarCategory } from "@/types/sidebar";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IApiQueryResponse {
  categories: Array<SidebarCategory>;
}

export const useGetCategoriesQuery: useQueryFunctionType<
  undefined,
  IApiQueryResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getCategoriesFn = async () => {
    return await api.get<IApiQueryResponse>(`${getURL("SIDEBAR_CATEGORIES")}`);
  };

  const responseFn = async () => {
    const { data } = await getCategoriesFn();
    return data;
  };

  const queryResult = query(["useGetCategoriesQuery"], responseFn, {
    ...options,
  });

  return queryResult;
};
