import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  AnnotationResultType,
  AnnotationResultUpdateType,
} from "@/types/annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PutImageAnnotationsArgs extends AnnotationResultUpdateType {
  projectId: string;
  imageId: string;
}

export const usePutImageAnnotations: useMutationFunctionType<
  undefined,
  PutImageAnnotationsArgs,
  AnnotationResultType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function putAnnotations({
    projectId,
    imageId,
    ...payload
  }: PutImageAnnotationsArgs): Promise<AnnotationResultType> {
    try {
      const { data } = await api.put<AnnotationResultType>(
        `${getURL("ANNOTATION_PROJECTS")}/${projectId}/images/${imageId}/annotations`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to save annotations",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    AnnotationResultType,
    Error,
    PutImageAnnotationsArgs
  > = mutate(["usePutImageAnnotations"], putAnnotations, {
    ...options,
    onSuccess: (data, variables, context) => {
      const args = variables as unknown as PutImageAnnotationsArgs;
      queryClient.setQueryData(["useGetImageAnnotations", args.imageId], data);
      queryClient.refetchQueries({
        queryKey: ["useGetAnnotationProject", args.projectId],
      });
      queryClient.refetchQueries({ queryKey: ["useGetAnnotationProjects"] });
      options?.onSuccess?.(data, variables, undefined, context as never);
    },
  });

  return mutation;
};
