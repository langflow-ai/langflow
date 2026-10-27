import type {
  useMutationFunctionType,
  useQueryFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type {
  CsvImportResult,
  CsvPreview,
  Dataset,
  DatasetItem,
  Page,
} from "./types";

const DATASETS_KEY = "useGetDatasets";
const DATASET_KEY = "useGetDataset";
const ITEMS_KEY = "useGetDatasetItems";

interface ListParams {
  search?: string;
  page?: number;
  size?: number;
}

export const useGetDatasets: useQueryFunctionType<ListParams, Page<Dataset>> = (
  { search = "", page = 1, size = 50 },
  options,
) => {
  const { query } = UseRequestProcessor();
  return query(
    [DATASETS_KEY, { search, page, size }],
    async () =>
      (
        await api.get<Page<Dataset>>(`${getURL("DATASETS")}/`, {
          params: { search: search || undefined, page, size },
        })
      ).data,
    options,
  );
};

export const useGetDataset: useQueryFunctionType<
  { datasetId: string },
  Dataset
> = ({ datasetId }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    [DATASET_KEY, datasetId],
    async () =>
      (await api.get<Dataset>(`${getURL("DATASETS")}/${datasetId}`)).data,
    { enabled: Boolean(datasetId), ...options },
  );
};

export const useGetDatasetItems: useQueryFunctionType<
  { datasetId: string } & ListParams,
  Page<DatasetItem>
> = ({ datasetId, search = "", page = 1, size = 50 }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    [ITEMS_KEY, datasetId, { search, page, size }],
    async () =>
      (
        await api.get<Page<DatasetItem>>(
          `${getURL("DATASETS")}/${datasetId}/items`,
          { params: { search: search || undefined, page, size } },
        )
      ).data,
    { enabled: Boolean(datasetId), ...options },
  );
};

function useInvalidateDatasets() {
  const { queryClient } = UseRequestProcessor();
  return (datasetId?: string) => {
    queryClient.invalidateQueries({ queryKey: [DATASETS_KEY] });
    if (datasetId) {
      queryClient.invalidateQueries({ queryKey: [DATASET_KEY, datasetId] });
      queryClient.invalidateQueries({ queryKey: [ITEMS_KEY, datasetId] });
    }
  };
}

export const useCreateDataset: useMutationFunctionType<
  undefined,
  { name: string; description?: string },
  Dataset
> = (options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateDatasets();
  return mutate(
    ["useCreateDataset"],
    async (payload) =>
      (await api.post<Dataset>(`${getURL("DATASETS")}/`, payload)).data,
    { retry: false, ...options, onSettled: () => invalidate() },
  );
};

export const useDeleteDataset: useMutationFunctionType<
  undefined,
  { datasetId: string }
> = (options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateDatasets();
  return mutate(
    ["useDeleteDataset"],
    async ({ datasetId }) =>
      (await api.delete(`${getURL("DATASETS")}/${datasetId}`)).data,
    { ...options, onSettled: () => invalidate() },
  );
};

export const useAddDatasetItems: useMutationFunctionType<
  { datasetId: string },
  { items: { input: string; expected_output: string | null }[] },
  DatasetItem[]
> = ({ datasetId }, options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateDatasets();
  return mutate(
    ["useAddDatasetItems", datasetId],
    async (payload) =>
      (
        await api.post<DatasetItem[]>(
          `${getURL("DATASETS")}/${datasetId}/items`,
          payload,
        )
      ).data,
    { retry: false, ...options, onSettled: () => invalidate(datasetId) },
  );
};

export const useUpdateDatasetItem: useMutationFunctionType<
  { datasetId: string },
  {
    itemId: string;
    input: string;
    expected_output: string | null;
  },
  DatasetItem
> = ({ datasetId }, options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateDatasets();
  return mutate(
    ["useUpdateDatasetItem", datasetId],
    async ({ itemId, input, expected_output }) =>
      (
        await api.patch<DatasetItem>(
          `${getURL("DATASETS")}/${datasetId}/items/${itemId}`,
          {
            input,
            expected_output,
            clear_expected_output: expected_output === null,
          },
        )
      ).data,
    { ...options, onSettled: () => invalidate(datasetId) },
  );
};

export const useDeleteDatasetItems: useMutationFunctionType<
  { datasetId: string },
  { ids: string[] }
> = ({ datasetId }, options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateDatasets();
  return mutate(
    ["useDeleteDatasetItems", datasetId],
    async (payload) =>
      (
        await api.post(
          `${getURL("DATASETS")}/${datasetId}/items/delete`,
          payload,
        )
      ).data,
    { ...options, onSettled: () => invalidate(datasetId) },
  );
};

export const usePreviewCsvImport: useMutationFunctionType<
  { datasetId: string },
  { file: File },
  CsvPreview
> = ({ datasetId }, options) => {
  const { mutate } = UseRequestProcessor();
  return mutate(
    ["usePreviewCsvImport", datasetId],
    async ({ file }) => {
      const form = new FormData();
      form.append("file", file);
      return (
        await api.post<CsvPreview>(
          `${getURL("DATASETS")}/${datasetId}/import/preview`,
          form,
        )
      ).data;
    },
    options,
  );
};

export const useImportCsv: useMutationFunctionType<
  { datasetId: string },
  { file: File; inputColumn: string; expectedColumn: string | null },
  CsvImportResult
> = ({ datasetId }, options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateDatasets();
  return mutate(
    ["useImportCsv", datasetId],
    async ({ file, inputColumn, expectedColumn }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("input_column", inputColumn);
      if (expectedColumn) form.append("expected_column", expectedColumn);
      return (
        await api.post<CsvImportResult>(
          `${getURL("DATASETS")}/${datasetId}/import`,
          form,
        )
      ).data;
    },
    { retry: false, ...options, onSettled: () => invalidate(datasetId) },
  );
};

export const useDuplicateDataset: useMutationFunctionType<
  undefined,
  { datasetId: string },
  Dataset
> = (options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateDatasets();
  return mutate(
    ["useDuplicateDataset"],
    async ({ datasetId }) =>
      (await api.post<Dataset>(`${getURL("DATASETS")}/${datasetId}/duplicate`))
        .data,
    { retry: false, ...options, onSettled: () => invalidate() },
  );
};
