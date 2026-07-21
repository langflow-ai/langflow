import type { useQueryFunctionType } from "@/types/api";
import type { TextAnnotationProjectType } from "@/types/text-annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type GetTextAnnotationProjectsResponse = TextAnnotationProjectType[];

export const useGetTextAnnotationProjects: useQueryFunctionType<
  undefined,
  GetTextAnnotationProjectsResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<GetTextAnnotationProjectsResponse> => {
    const { data } = await api.get<GetTextAnnotationProjectsResponse>(
      `${getURL("TEXT_ANNOTATION_PROJECTS")}/`,
    );
    return data;
  };

  return query(["useGetTextAnnotationProjects"], responseFn, options ?? {});
};
