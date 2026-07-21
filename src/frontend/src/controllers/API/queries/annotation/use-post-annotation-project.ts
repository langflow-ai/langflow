import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  AnnotationProjectCreateType,
  AnnotationProjectType,
} from "@/types/annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

export const usePostAnnotationProject: useMutationFunctionType<
  undefined,
  AnnotationProjectCreateType,
  AnnotationProjectType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function createProject(
    payload: AnnotationProjectCreateType,
  ): Promise<AnnotationProjectType> {
    try {
      const { data } = await api.post<AnnotationProjectType>(
        `${getURL("ANNOTATION_PROJECTS")}/`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to create annotation project",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    AnnotationProjectType,
    Error,
    AnnotationProjectCreateType
  > = mutate(["usePostAnnotationProject"], createProject, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.refetchQueries({ queryKey: ["useGetAnnotationProjects"] });
      options?.onSuccess?.(data, variables, undefined, context as never);
    },
  });

  return mutation;
};
