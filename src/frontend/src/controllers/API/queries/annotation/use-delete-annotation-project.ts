import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteAnnotationProjectArgs {
  projectId: string;
}

export const useDeleteAnnotationProject: useMutationFunctionType<
  undefined,
  DeleteAnnotationProjectArgs,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function deleteProject({
    projectId,
  }: DeleteAnnotationProjectArgs): Promise<void> {
    try {
      await api.delete(`${getURL("ANNOTATION_PROJECTS")}/${projectId}`);
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to delete annotation project",
        ),
      );
    }
  }

  const mutation: UseMutationResult<void, Error, DeleteAnnotationProjectArgs> =
    mutate(["useDeleteAnnotationProject"], deleteProject, {
      ...options,
      onSuccess: (data, variables, context) => {
        queryClient.refetchQueries({ queryKey: ["useGetAnnotationProjects"] });
        options?.onSuccess?.(data, variables, undefined, context as never);
      },
    });

  return mutation;
};
