import type { ProjectTypeType } from "@/pages/MainPage/entities";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

/**
 * The project types and the form each one renders.
 *
 * The vocabulary only changes when the server changes, so this is cached for the session
 * rather than refetched per project.
 */
export const useGetProjectTypesQuery: useQueryFunctionType<
  undefined,
  ProjectTypeType[]
> = (options) => {
  const { query } = UseRequestProcessor();

  const getProjectTypesFn = async (): Promise<ProjectTypeType[]> => {
    const res = await api.get(`${getURL("PROJECTS")}/types`);
    return res.data;
  };

  return query(["useGetProjectTypes"], getProjectTypesFn, {
    staleTime: Infinity,
    ...options,
  });
};
