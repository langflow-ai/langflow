import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { AnnotationImageType } from "@/types/annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PostAnnotationImagesArgs {
  projectId: string;
  files: File[];
}

export const usePostAnnotationImages: useMutationFunctionType<
  undefined,
  PostAnnotationImagesArgs,
  AnnotationImageType[]
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function uploadImages({
    projectId,
    files,
  }: PostAnnotationImagesArgs): Promise<AnnotationImageType[]> {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file, file.name);
    }
    try {
      const { data } = await api.post<AnnotationImageType[]>(
        `${getURL("ANNOTATION_PROJECTS")}/${projectId}/images`,
        formData,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to upload images",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    AnnotationImageType[],
    Error,
    PostAnnotationImagesArgs
  > = mutate(["usePostAnnotationImages"], uploadImages, {
    ...options,
    onSuccess: (data, variables, context) => {
      const args = variables as unknown as PostAnnotationImagesArgs;
      queryClient.refetchQueries({
        queryKey: ["useGetAnnotationProject", args.projectId],
      });
      queryClient.refetchQueries({ queryKey: ["useGetAnnotationProjects"] });
      options?.onSuccess?.(data, variables, undefined, context as never);
    },
  });

  return mutation;
};
