import { FolderType, PaginatedFolderType } from "@/pages/MainPage/entities";
import { useQueryFunctionType } from "@/types/api";
import { UseQueryOptions } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetFolder {
  id: string;
  page?: number;
  size?: number;
  is_component?: boolean;
  is_flow?: boolean;
  search?: string;
}

const addQueryParams = (url: string, params: IGetFolder): string => {
  const queryParams = new URLSearchParams();
  if (params.page) queryParams.append("page", params.page.toString());
  if (params.size) queryParams.append("size", params.size.toString());
  if (params.is_component)
    queryParams.append("is_component", params.is_component.toString());
  if (params.is_flow) queryParams.append("is_flow", params.is_flow.toString());
  if (params.search) queryParams.append("search", params.search);
  const queryString = queryParams.toString();
  return queryString ? `${url}?${queryString}` : url;
};

export const useGetFolderQuery: useQueryFunctionType<
  IGetFolder,
  PaginatedFolderType
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getFolderFn = async (
    params: IGetFolder,
  ): Promise<PaginatedFolderType> => {
    const url = addQueryParams(`${getURL("FOLDERS")}/${params.id}`, params);
    const { data } = await api.get<PaginatedFolderType>(url);
    return data;
  };

  const queryResult = query(
    ["useGetFolder", params],
    () => getFolderFn(params),
    options as UseQueryOptions<any, Error, PaginatedFolderType, any>,
  );

  return queryResult;
};
