import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  DatabaseImportPreviewRequestType,
  DatabaseImportPreviewResponseType,
  DatabaseImportRequestType,
  TextAnnotationImportResponseType,
} from "@/types/text-annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PreviewDatabaseImportArgs extends DatabaseImportPreviewRequestType {
  projectId: string;
}

interface PostDatabaseImportArgs extends DatabaseImportRequestType {
  projectId: string;
}

export const usePreviewTextAnnotationDatabaseImport: useMutationFunctionType<
  undefined,
  PreviewDatabaseImportArgs,
  DatabaseImportPreviewResponseType
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function preview({
    projectId,
    ...payload
  }: PreviewDatabaseImportArgs): Promise<DatabaseImportPreviewResponseType> {
    try {
      const { data } = await api.post<DatabaseImportPreviewResponseType>(
        `${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}/import/database/preview`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to connect to database",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    DatabaseImportPreviewResponseType,
    Error,
    PreviewDatabaseImportArgs
  > = mutate(["usePreviewTextAnnotationDatabaseImport"], preview, {
    ...(options ?? {}),
  });

  return mutation;
};

export const usePostTextAnnotationImportDatabase: useMutationFunctionType<
  undefined,
  PostDatabaseImportArgs,
  TextAnnotationImportResponseType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function importDatabase({
    projectId,
    ...payload
  }: PostDatabaseImportArgs): Promise<TextAnnotationImportResponseType> {
    try {
      const { data } = await api.post<TextAnnotationImportResponseType>(
        `${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}/import/database`,
        payload,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to import from database",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    TextAnnotationImportResponseType,
    Error,
    PostDatabaseImportArgs
  > = mutate(["usePostTextAnnotationImportDatabase"], importDatabase, {
    ...options,
    onSuccess: (data, variables, context) => {
      const args = variables as unknown as PostDatabaseImportArgs;
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
