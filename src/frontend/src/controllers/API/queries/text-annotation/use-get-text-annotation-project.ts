import type { useQueryFunctionType } from "@/types/api";
import type { TextAnnotationProjectDetailType } from "@/types/text-annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface GetTextAnnotationProjectParams {
  projectId: string;
  enabled?: boolean;
}

export const useGetTextAnnotationProject: useQueryFunctionType<
  GetTextAnnotationProjectParams,
  TextAnnotationProjectDetailType
> = ({ projectId, enabled }, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<TextAnnotationProjectDetailType> => {
    const { data } = await api.get<TextAnnotationProjectDetailType>(
      `${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}`,
    );
    return data;
  };

  return query(["useGetTextAnnotationProject", projectId], responseFn, {
    enabled: enabled ?? true,
    ...(options ?? {}),
  });
};
