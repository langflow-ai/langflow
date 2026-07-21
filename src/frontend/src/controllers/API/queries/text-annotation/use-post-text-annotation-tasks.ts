import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  TextAnnotationTaskCreateType,
  TextAnnotationTaskItemType,
} from "@/types/text-annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PostTextAnnotationTasksArgs {
  projectId: string;
  tasks: TextAnnotationTaskCreateType[];
  source?: string;
}

export const usePostTextAnnotationTasks: useMutationFunctionType<
  undefined,
  PostTextAnnotationTasksArgs,
  TextAnnotationTaskItemType[]
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function postTasks({
    projectId,
    tasks,
    source,
  }: PostTextAnnotationTasksArgs): Promise<TextAnnotationTaskItemType[]> {
    try {
      const { data } = await api.post<TextAnnotationTaskItemType[]>(
        `${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}/tasks`,
        { tasks, source: source ?? "paste" },
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to add texts",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    TextAnnotationTaskItemType[],
    Error,
    PostTextAnnotationTasksArgs
  > = mutate(["usePostTextAnnotationTasks"], postTasks, {
    ...options,
    onSuccess: (data, variables, context) => {
      const args = variables as unknown as PostTextAnnotationTasksArgs;
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
