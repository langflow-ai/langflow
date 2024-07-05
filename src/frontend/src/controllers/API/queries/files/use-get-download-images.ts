import { keepPreviousData } from "@tanstack/react-query";
import { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DownloadImagesQueryParams {
  flowId: string;
  fileName: string;
}

export interface DownloadImagesResponse {
  response: string;
}

export const useGetDownloadImagesQuery: useQueryFunctionType<
  DownloadImagesQueryParams,
  DownloadImagesResponse
> = (params) => {
  const { query } = UseRequestProcessor();

  const getDownloadImagesFn = async () => {
    if (!params) return;
    const response = await api.get<DownloadImagesResponse>(
      `${getURL("FILES")}/images/${params.flowId}/${params.fileName}`,
    );
    return response["data"];
  };

  const queryResult = query(
    ["useGetDownloadImagesQuery"],
    getDownloadImagesFn,
    {
      placeholderData: keepPreviousData,
    },
  );

  return queryResult;
};
