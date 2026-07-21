import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { TextAnnotationImportResponseType } from "@/types/text-annotation";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PostTextAnnotationImportCsvArgs {
  projectId: string;
  file: File;
  textColumn?: string;
  nameColumn?: string;
  hasHeader?: boolean;
}

export const usePostTextAnnotationImportCsv: useMutationFunctionType<
  undefined,
  PostTextAnnotationImportCsvArgs,
  TextAnnotationImportResponseType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function importCsv({
    projectId,
    file,
    textColumn,
    nameColumn,
    hasHeader,
  }: PostTextAnnotationImportCsvArgs): Promise<TextAnnotationImportResponseType> {
    const formData = new FormData();
    formData.append("file", file, file.name);
    if (textColumn) formData.append("text_column", textColumn);
    if (nameColumn) formData.append("name_column", nameColumn);
    formData.append("has_header", String(hasHeader ?? true));
    try {
      const { data } = await api.post<TextAnnotationImportResponseType>(
        `${getURL("TEXT_ANNOTATION_PROJECTS")}/${projectId}/import/csv`,
        formData,
      );
      return data;
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to import CSV",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    TextAnnotationImportResponseType,
    Error,
    PostTextAnnotationImportCsvArgs
  > = mutate(["usePostTextAnnotationImportCsv"], importCsv, {
    ...options,
    onSuccess: (data, variables, context) => {
      const args = variables as unknown as PostTextAnnotationImportCsvArgs;
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
