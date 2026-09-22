import type { PaginatedFolderType } from "@/pages/MainPage/entities";
import type { useQueryFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetProjectFlows {
  projectId: string;
}

/**
 * The most the endpoint accepts. `custom_params` builds a fastapi-pagination `Params` directly,
 * and that caps size at 100; asking for more does not come back as a validation error, the
 * request just never returns.
 */
const PAGE_SIZE = 100;

/**
 * The flows in a project, for a form that composes them.
 *
 * Deliberately separate from `useGetFolderQuery`: that one backs the project page, writes to the
 * folder and flow stores and is paged by whichever tab is open. This one only reads, so a form
 * asking "which flows live here" cannot disturb the page around it.
 */
export const useGetProjectFlowsQuery: useQueryFunctionType<
  IGetProjectFlows,
  FlowType[]
> = ({ projectId }, options) => {
  const { query } = UseRequestProcessor();

  const getProjectFlowsFn = async (): Promise<FlowType[]> => {
    const flows: FlowType[] = [];
    let page = 1;
    let pages = 1;
    do {
      const { data } = await api.get<PaginatedFolderType>(
        `${getURL("PROJECTS")}/${projectId}?is_flow=true&page=${page}&size=${PAGE_SIZE}`,
      );
      flows.push(...(data?.flows?.items ?? []));
      pages = data?.flows?.pages ?? page;
      page += 1;
    } while (page <= pages);
    return flows;
  };

  return query(["useGetProjectFlows", projectId], getProjectFlowsFn, {
    enabled: Boolean(projectId),
    ...options,
  });
};
