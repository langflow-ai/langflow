import { keepPreviousData } from "@tanstack/react-query";
import {
  useMutationFunctionType,
  useQueryFunctionType,
} from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DownloadImagesQueryParams {
  path: string;
  filename: string;
}

export const useGetDownloadFileMutation: useMutationFunctionType<
  DownloadImagesQueryParams
> = (params, options) => {
  const { mutate } = UseRequestProcessor();

  const getDownloadImagesFn = async () => {
    if (!params) return;
    // need to use fetch because axios convert blob data to string, and this convertion can corrupt the file
    const response = await fetch(`${getURL("FILES")}/download/${params.path}`, {
      headers: {
        Accept: "*/*",
      },
    });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", params.filename); // Set the filename
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
    return {};
  };

  const queryResult = mutate(
    ["useGetDownloadFileMutation", params.path],
    getDownloadImagesFn,
    options,
  );

  return queryResult;
};
