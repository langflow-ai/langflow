import type { ProjectListType } from "@/pages/MainPage/entities";
import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import type { PaginatedFlowsType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface SharedResources {
  flows: PaginatedFlowsType;
  projects: PaginatedProjects;
}

export interface SharedResourcesParams {
  flowPage: number;
  flowSize: number;
  projectPage: number;
  projectSize: number;
}

export interface PaginatedProjects {
  items: ProjectListType[];
  total: number;
  size: number;
  page: number;
  pages: number;
}

export const useGetSharedResources: useQueryFunctionType<
  SharedResourcesParams,
  SharedResources
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const userId = useAuthStore((state) => state.userData?.id);
  return query(
    ["authorizationSharedResources", userId ?? "anonymous", params],
    async () => {
      const [flows, projects] = await Promise.all([
        api.get<PaginatedFlowsType>(`${getURL("FLOWS")}/`, {
          params: {
            get_all: false,
            shared_only: true,
            page: params.flowPage,
            size: params.flowSize,
          },
        }),
        api.get<PaginatedProjects>(`${getURL("PROJECTS")}/`, {
          params: {
            get_all: false,
            shared_only: true,
            page: params.projectPage,
            size: params.projectSize,
          },
        }),
      ]);
      return { flows: flows.data, projects: projects.data };
    },
    {
      staleTime: 15_000,
      ...options,
      enabled: Boolean(userId) && (options?.enabled ?? true),
    },
  );
};
