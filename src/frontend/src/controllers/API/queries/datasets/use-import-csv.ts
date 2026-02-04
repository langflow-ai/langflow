import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ImportCsvParams {
  datasetId: string;
  file: File;
  inputColumn: string;
  expectedOutputColumn: string;
}

export const useImportCsv: useMutationFunctionType<undefined, ImportCsvParams> =
  (options?) => {
    const { mutate, queryClient } = UseRequestProcessor();

    const importCsvFn = async (
      params: ImportCsvParams,
    ): Promise<{ imported: number }> => {
      const formData = new FormData();
      formData.append("file", params.file);

      const response = await api.post<{ imported: number }>(
        `${getURL("DATASETS")}/${params.datasetId}/import/csv?input_column=${encodeURIComponent(params.inputColumn)}&expected_output_column=${encodeURIComponent(params.expectedOutputColumn)}`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        },
      );
      queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
      queryClient.invalidateQueries({
        queryKey: ["useGetDataset", params.datasetId],
      });
      return response.data;
    };

    const mutation: UseMutationResult<
      { imported: number },
      any,
      ImportCsvParams
    > = mutate(["useImportCsv"], importCsvFn, options);

    return mutation;
  };
