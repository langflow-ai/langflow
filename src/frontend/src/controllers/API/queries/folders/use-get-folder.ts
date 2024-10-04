import buildQueryStringUrl from "@/controllers/utils/create-query-param-string";
import { FolderType, PaginatedFolderType } from "@/pages/MainPage/entities";
import { useFolderStore } from "@/stores/foldersStore";
import { useQueryFunctionType } from "@/types/api";
import { processFlows } from "@/utils/reactflowUtils";
import { UseQueryOptions } from "@tanstack/react-query";
import { cloneDeep } from "lodash";
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
  return buildQueryStringUrl(url, params);
};

export const useGetFolderQuery: useQueryFunctionType<
  IGetFolder,
  PaginatedFolderType | undefined
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const folders = useFolderStore((state) => state.folders);

  const getFolderFn = async (
    params: IGetFolder,
  ): Promise<PaginatedFolderType | undefined> => {
    if (params.id) {
      const existingFolder = folders.find((f) => f.id === params.id);
      if (!existingFolder) {
        return;
      }
    }

    const url = addQueryParams(`${getURL("FOLDERS")}/${params.id}`, params);
    const { data } = await api.get<PaginatedFolderType>(url);

    const { flows } = processFlows(data.flows.items);

    const dataProcessed = cloneDeep(data);
    dataProcessed.flows.items = flows;

    return dataProcessed;
  };

  const queryResult = query(
    [
      "useGetFolder",
      params.id,
      {
        page: params.page,
        size: params.size,
        is_component: params.is_component,
        is_flow: params.is_flow,
        search: params.search,
      },
    ],
    () => getFolderFn(params),
    {
      refetchOnWindowFocus: false,
      placeholderData: true,
      ...options,
    },
  );

  return queryResult;
};
