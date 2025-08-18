import type { useMutationFunctionType } from "../../../../types/api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DownloadFileQueryParams {
  id: string;
  filename: string;
  type: string;
}

export const useGetDownloadFileV2: useMutationFunctionType<
  DownloadFileQueryParams,
  void
> = (params, options) => {
  const { mutate } = UseRequestProcessor();

  const getDownloadFileFn = async () => {
    if (!params) return;
    // need to use fetch because axios convert blob data to string, and this convertion can corrupt the file
    const response = await fetch(
      `${getURL("FILE_MANAGEMENT", { id: params.id }, true)}`,
      {
        headers: {
          Accept: "*/*",
        },
      },
    );
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", params.filename + "." + params.type); // Set the filename
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
    return {};
  };

  const queryResult = mutate(
    ["useGetDownloadFileV2", params.id],
    getDownloadFileFn,
    options,
  );

  return queryResult;
};
