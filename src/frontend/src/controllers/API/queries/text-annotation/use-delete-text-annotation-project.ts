import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteTextAnnotationProjectArgs {
  projectId: string;
}

export const useDeleteTextAnnotationProject: useMutationFunctionType<
  undefined,
  DeleteTextAnnotationProjectArgs,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function deleteProject({
    projectId,
  }: DeleteTextAnnotationProjectArgs): Promise<void> {
    try {
      await api.delete(`${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}`);
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to delete text annotation project",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    void,
    Error,
    DeleteTextAnnotationProjectArgs
  > = mutate(["useDeleteTextAnnotationProject"], deleteProject, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.refetchQueries({
        queryKey: ["useGetTextAnnotationProjects"],
      });
      options?.onSuccess?.(data, variables, undefined, context as never);
    },
  });

  return mutation;
};
