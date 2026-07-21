import type { useQueryFunctionType } from "@/types/api";
import type { AnnotationProjectType } from "@/types/annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type GetAnnotationProjectsResponse = AnnotationProjectType[];

export const useGetAnnotationProjects: useQueryFunctionType<
  undefined,
  GetAnnotationProjectsResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<GetAnnotationProjectsResponse> => {
    const { data } = await api.get<GetAnnotationProjectsResponse>(
      `${getURL("ANNOTATION_PROJECTS")}/`,
    );
    return data;
  };

  return query(["useGetAnnotationProjects"], responseFn, options ?? {});
};
