import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  TextAnnotationRegion,
  TextAnnotationResultType,
} from "@/types/text-annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PutTextTaskAnnotationsArgs {
  projectId: string;
  taskId: string;
  result: TextAnnotationRegion[];
  lead_time?: number;
}

export const usePutTextTaskAnnotations: useMutationFunctionType<
  undefined,
  PutTextTaskAnnotationsArgs,
  TextAnnotationResultType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function putAnnotations({
    projectId,
    taskId,
    ...payload
  }: PutTextTaskAnnotationsArgs): Promise<TextAnnotationResultType> {
    try {
      const { data } = await api.put<TextAnnotationResultType>(
        `${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}/tasks/${taskId}/annotations`,
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
    TextAnnotationResultType,
    Error,
    PutTextTaskAnnotationsArgs
  > = mutate(["usePutTextTaskAnnotations"], putAnnotations, {
    ...options,
    onSuccess: (data, variables, context) => {
      const args = variables as unknown as PutTextTaskAnnotationsArgs;
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
