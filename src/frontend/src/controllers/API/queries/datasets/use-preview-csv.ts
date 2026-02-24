import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PreviewCsvParams {
  file: File;
}

interface CsvPreviewResult {
  columns: string[];
  preview: Record<string, string>[];
}

export const usePreviewCsv: useMutationFunctionType<
  undefined,
  PreviewCsvParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const previewCsvFn = async (
    params: PreviewCsvParams,
  ): Promise<CsvPreviewResult> => {
    const formData = new FormData();
    formData.append("file", params.file);

    const response = await api.post<CsvPreviewResult>(
      `${getURL("DATASETS")}/preview-csv`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
    return response.data;
  };

  const mutation: UseMutationResult<CsvPreviewResult, any, PreviewCsvParams> =
    mutate(["usePreviewCsv"], previewCsvFn, {
      ...options,
    });

  return mutation;
};
