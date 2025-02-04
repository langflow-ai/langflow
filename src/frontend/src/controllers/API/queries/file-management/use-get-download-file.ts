import { useMutationFunctionType } from "../../../../types/api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DownloadFileQueryParams {
  id: string;
  filename: string;
}

export const useGetDownloadFileV2: useMutationFunctionType<
  DownloadFileQueryParams
> = (params, options) => {
  const { mutate } = UseRequestProcessor();

  const getDownloadFileFn = async () => {
    if (!params) return;
    // need to use fetch because axios convert blob data to string, and this convertion can corrupt the file
    const response = await fetch(`${getURL("FILE_MANAGEMENT")}/${params.id}`, {
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
    ["useGetDownloadFileV2", params.id],
    getDownloadFileFn,
    options,
  );

  return queryResult;
};
