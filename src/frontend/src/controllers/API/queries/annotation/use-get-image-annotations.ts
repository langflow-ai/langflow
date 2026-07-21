import type { useQueryFunctionType } from "@/types/api";
import type { AnnotationResultType } from "@/types/annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface GetImageAnnotationsParams {
  projectId: string;
  imageId: string | null;
}

export const useGetImageAnnotations: useQueryFunctionType<
  GetImageAnnotationsParams,
  AnnotationResultType
> = ({ projectId, imageId }, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<AnnotationResultType> => {
    const { data } = await api.get<AnnotationResultType>(
      `${getURL("ANNOTATION_PROJECTS")}/${projectId}/images/${imageId}/annotations`,
    );
    return data;
  };

  return query(["useGetImageAnnotations", imageId], responseFn, {
    enabled: Boolean(imageId),
    ...(options ?? {}),
  });
};
