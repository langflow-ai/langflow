import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  TextAnnotationProjectType,
  TextAnnotationProjectUpdateType,
} from "@/types/text-annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchTextAnnotationProjectArgs
  extends TextAnnotationProjectUpdateType {
  projectId: string;
}

export const usePatchTextAnnotationProject: useMutationFunctionType<
  undefined,
  PatchTextAnnotationProjectArgs,
  TextAnnotationProjectType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchProject({
    projectId,
    ...payload
  }: PatchTextAnnotationProjectArgs): Promise<TextAnnotationProjectType> {
    try {
      const { data } = await api.patch<TextAnnotationProjectType>(
        `${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to update text annotation project",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    TextAnnotationProjectType,
    Error,
    PatchTextAnnotationProjectArgs
  > = mutate(["usePatchTextAnnotationProject"], patchProject, {
    ...options,
    onSuccess: (data, variables, context) => {
      const args = variables as unknown as PatchTextAnnotationProjectArgs;
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
