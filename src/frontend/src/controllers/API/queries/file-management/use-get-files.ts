import type { FileType } from "@/types/file_management";
import { keepPreviousData } from "@tanstack/react-query";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type FilesResponse = FileType[];

export const useGetFilesV2: useQueryFunctionType<undefined, FilesResponse> = (
  config,
) => {
  const { query } = UseRequestProcessor();

  const getFilesFn = async () => {
    const response = await api.get<FilesResponse>(
      `${getURL("FILE_MANAGEMENT", {}, true)}`,
    );
    return response["data"] ?? [];
  };

  const queryResult = query(["useGetFilesV2"], getFilesFn, {
    placeholderData: keepPreviousData,
    ...config,
  });

  return queryResult;
};
