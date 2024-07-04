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

  const getDownloadImagesFn = async ({
    flowId,
    fileName,
  }: {
    flowId: string;
    fileName: string;
  }) => {
    return await api.get<DownloadImagesResponse>(
      `${getURL("FILES")}/images/${flowId}/${fileName}`,
    );
  };

  const queryResult = query(
    ["useGetDownloadImagesQuery"],
    async () => {
      const response = await getDownloadImagesFn({
        flowId,
        fileName,
      });
      return response["data"];
    },
    {
      placeholderData: keepPreviousData,
    },
  );

  return queryResult;
};
