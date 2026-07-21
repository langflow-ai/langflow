import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  AnnotationImageType,
  AnnotationImageUpdateType,
} from "@/types/annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchAnnotationImageArgs extends AnnotationImageUpdateType {
  projectId: string;
  imageId: string;
}

export const usePatchAnnotationImage: useMutationFunctionType<
  undefined,
  PatchAnnotationImageArgs,
  AnnotationImageType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchImage({
    projectId,
    imageId,
    ...payload
  }: PatchAnnotationImageArgs): Promise<AnnotationImageType> {
    try {
      const { data } = await api.patch<AnnotationImageType>(
        `${getURL("ANNOTATION_PROJECTS")}/${projectId}/images/${imageId}`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to update image",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    AnnotationImageType,
    Error,
    PatchAnnotationImageArgs
  > = mutate(["usePatchAnnotationImage"], patchImage, {
    ...options,
    onSuccess: (data, variables, context) => {
      const args = variables as unknown as PatchAnnotationImageArgs;
      queryClient.refetchQueries({
        queryKey: ["useGetAnnotationProject", args.projectId],
      });
      options?.onSuccess?.(data, variables, undefined, context as never);
    },
  });

  return mutation;
};
