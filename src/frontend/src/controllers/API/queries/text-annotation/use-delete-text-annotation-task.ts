import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteTextAnnotationTaskArgs {
  projectId: string;
  taskId: string;
}

export const useDeleteTextAnnotationTask: useMutationFunctionType<
  undefined,
  DeleteTextAnnotationTaskArgs,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function deleteTask({
    projectId,
    taskId,
  }: DeleteTextAnnotationTaskArgs): Promise<void> {
    try {
      await api.delete(
        `${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}/tasks/${taskId}`,
      );
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to delete text",
        ),
      );
    }
  }

  const mutation: UseMutationResult<void, Error, DeleteTextAnnotationTaskArgs> =
    mutate(["useDeleteTextAnnotationTask"], deleteTask, {
      ...options,
      onSuccess: (data, variables, context) => {
        const args = variables as unknown as DeleteTextAnnotationTaskArgs;
        queryClient.refetchQueries({
          queryKey: ["useGetTextAnnotationProject", args.projectId],
        });
        queryClient.refetchQueries({
          queryKey: ["useGetTextAnnotationProjects"],
        });
        options?.onSuccess?.(data, variables, undefined, context as never);
      },
    });

  return mutation;
};
