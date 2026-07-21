import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  TextAnnotationProjectCreateType,
  TextAnnotationProjectType,
} from "@/types/text-annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

export const usePostTextAnnotationProject: useMutationFunctionType<
  undefined,
  TextAnnotationProjectCreateType,
  TextAnnotationProjectType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function createProject(
    payload: TextAnnotationProjectCreateType,
  ): Promise<TextAnnotationProjectType> {
    try {
      const { data } = await api.post<TextAnnotationProjectType>(
        `${getURL("TEXT_ANNOTATION_PROJECTS")}/`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to create text annotation project",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    TextAnnotationProjectType,
    Error,
    TextAnnotationProjectCreateType
  > = mutate(["usePostTextAnnotationProject"], createProject, {
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
