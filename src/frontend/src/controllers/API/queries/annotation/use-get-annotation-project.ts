import type { useQueryFunctionType } from "@/types/api";
import type { AnnotationProjectDetailType } from "@/types/annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface GetAnnotationProjectParams {
  projectId: string;
  enabled?: boolean;
}

export const useGetAnnotationProject: useQueryFunctionType<
  GetAnnotationProjectParams,
  AnnotationProjectDetailType
> = ({ projectId, enabled }, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<AnnotationProjectDetailType> => {
    const { data } = await api.get<AnnotationProjectDetailType>(
      `${getURL("ANNOTATION_PROJECTS")}/${projectId}`,
    );
    return data;
  };

  return query(["useGetAnnotationProject", projectId], responseFn, {
    enabled: enabled ?? true,
    ...(options ?? {}),
  });
};
