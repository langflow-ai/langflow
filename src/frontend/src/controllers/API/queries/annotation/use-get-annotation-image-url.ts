import { useEffect } from "react";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface GetAnnotationImageUrlParams {
  projectId: string;
  imageId: string | null;
}

/**
 * Fetch an annotation image through the authenticated API and expose it as a
 * blob object URL (plain <img src> cannot attach credentials).
 * The object URL is revoked when the query data changes or the component
 * using the hook unmounts.
 */
export const useGetAnnotationImageUrl: useQueryFunctionType<
  GetAnnotationImageUrlParams,
  string
> = ({ projectId, imageId }, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<string> => {
    const { data } = await api.get<Blob>(
      `${getURL("ANNOTATION_PROJECTS")}/${projectId}/images/${imageId}/file`,
      { responseType: "blob" },
    );
    return URL.createObjectURL(data);
  };

  const result = query(["useGetAnnotationImageUrl", imageId], responseFn, {
    enabled: Boolean(imageId),
    // Image binaries are immutable once uploaded, so no refetch is needed.
    staleTime: Number.POSITIVE_INFINITY,
    ...(options ?? {}),
  });

  const url = result.data;
  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [url]);

  return result;
};
