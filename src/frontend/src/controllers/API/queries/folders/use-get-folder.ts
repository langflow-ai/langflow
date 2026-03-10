import { cloneDeep } from "lodash";
import { useRef } from "react";
import buildQueryStringUrl from "@/controllers/utils/create-query-param-string";
import type { PaginatedFolderType } from "@/pages/MainPage/entities";
import { useFolderStore } from "@/stores/foldersStore";
import type { useQueryFunctionType } from "@/types/api";
import type { PaginatedFlowsType } from "@/types/flow";
import { processFlows } from "@/utils/reactflowUtils";
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

type GetFlowsQueryParams = {
  get_all: boolean;
  header_flows: boolean;
  folder_id: string;
  page?: number;
  size?: number;
};

export const useGetFolderQuery: useQueryFunctionType<
  IGetFolder,
  PaginatedFolderType | undefined
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const folders = useFolderStore((state) => state.folders);
  const latestIdRef = useRef("");

  const getFolderFn = async (
    params: IGetFolder,
  ): Promise<PaginatedFolderType | undefined> => {
    if (params.id) {
      if (latestIdRef.current !== params.id) {
        params.page = 1;
      }
      latestIdRef.current = params.id;

      const existingFolder = folders.find((f) => f.id === params.id);
      if (!existingFolder) {
        return;
      }

      if (params.is_flow && !params.search) {
        const flowsUrl = buildQueryStringUrl(`${getURL("FLOWS")}/`, {
          get_all: false,
          header_flows: true,
          folder_id: params.id,
          page: params.page,
          size: params.size,
        } satisfies GetFlowsQueryParams);
        const { data } = await api.get<PaginatedFlowsType>(flowsUrl);
        const { flows } = processFlows(
          data.items.filter((flow) => !flow.is_component),
        );

        return {
          folder: {
            name: existingFolder.name,
            description: existingFolder.description ?? "",
            id: existingFolder.id,
            parent_id: existingFolder.parent_id ?? "",
            components: existingFolder.components ?? [],
          },
          flows: {
            items: flows,
            total: data.total,
            page: data.page,
            size: data.size,
            pages: data.pages,
          },
        };
      }
    }

    const url = addQueryParams(`${getURL("PROJECTS")}/${params.id}`, {
      page: params.page,
      size: params.size,
      is_component: params.is_component,
      is_flow: params.is_flow,
      search: params.search,
    });
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
      ...options,
    },
  );

  return queryResult;
};
