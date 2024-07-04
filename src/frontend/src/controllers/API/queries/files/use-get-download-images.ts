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
> = ({ flowId, fileName }) => {
  const { query } = UseRequestProcessor();

  const getDownloadImagesFn = async () => {
    const response = await api.get<DownloadImagesResponse>(
      `${getURL("FILES")}/images/${flowId}/${fileName}`,
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
