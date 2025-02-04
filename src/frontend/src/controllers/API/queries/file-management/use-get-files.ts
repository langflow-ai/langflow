import { FileType } from "@/types/file_management";
import { keepPreviousData } from "@tanstack/react-query";
import { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type FilesResponse = FileType[];

export const useGetFilesV2: useQueryFunctionType<undefined, FilesResponse> = (
  params,
) => {
  const { query } = UseRequestProcessor();

  const getFilesFn = async () => {
    if (!params) return;
    const response = await api.get<FilesResponse>(
      `${getURL("FILE_MANAGEMENT")}/`,
    );
    return response["data"];
  };

  const queryResult = query(["useGetFilesV2"], getFilesFn, {
    placeholderData: keepPreviousData,
  });

  return queryResult;
};
