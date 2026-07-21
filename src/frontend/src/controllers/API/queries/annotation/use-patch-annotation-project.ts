import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  AnnotationProjectType,
  AnnotationProjectUpdateType,
} from "@/types/annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchAnnotationProjectArgs extends AnnotationProjectUpdateType {
  projectId: string;
}

export const usePatchAnnotationProject: useMutationFunctionType<
  undefined,
  PatchAnnotationProjectArgs,
  AnnotationProjectType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchProject({
    projectId,
    ...payload
  }: PatchAnnotationProjectArgs): Promise<AnnotationProjectType> {
    try {
      const { data } = await api.patch<AnnotationProjectType>(
        `${getURL("ANNOTATION_PROJECTS")}/${projectId}`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to update annotation project",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    AnnotationProjectType,
    Error,
    PatchAnnotationProjectArgs
  > = mutate(["usePatchAnnotationProject"], patchProject, {
    ...options,
    onSuccess: (data, variables, context) => {
      const args = variables as unknown as PatchAnnotationProjectArgs;
      queryClient.refetchQueries({ queryKey: ["useGetAnnotationProjects"] });
      queryClient.refetchQueries({
        queryKey: ["useGetAnnotationProject", args.projectId],
      });
      options?.onSuccess?.(data, variables, undefined, context as never);
    },
  });

  return mutation;
};
