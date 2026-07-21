import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteAnnotationImageArgs {
  projectId: string;
  imageId: string;
}

export const useDeleteAnnotationImage: useMutationFunctionType<
  undefined,
  DeleteAnnotationImageArgs,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function deleteImage({
    projectId,
    imageId,
  }: DeleteAnnotationImageArgs): Promise<void> {
    try {
      await api.delete(
        `${getURL("ANNOTATION_PROJECTS")}/${projectId}/images/${imageId}`,
      );
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to delete image",
        ),
      );
    }
  }

  const mutation: UseMutationResult<void, Error, DeleteAnnotationImageArgs> =
    mutate(["useDeleteAnnotationImage"], deleteImage, {
      ...options,
      onSuccess: (data, variables, context) => {
        const args = variables as unknown as DeleteAnnotationImageArgs;
        queryClient.refetchQueries({
          queryKey: ["useGetAnnotationProject", args.projectId],
        });
        queryClient.refetchQueries({ queryKey: ["useGetAnnotationProjects"] });
        queryClient.removeQueries({
          queryKey: ["useGetAnnotationImageUrl", args.imageId],
        });
        queryClient.removeQueries({
          queryKey: ["useGetImageAnnotations", args.imageId],
        });
        options?.onSuccess?.(data, variables, undefined, context as never);
      },
    });

  return mutation;
};
