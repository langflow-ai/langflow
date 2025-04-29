import { useMutationFunctionType } from "../../../../types/api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DownloadFlowsQueryParams {
  ids: string[];
}

export const useGetDownloadFlows: useMutationFunctionType<
  undefined,
  DownloadFlowsQueryParams
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const getDownloadFlowsFn = async (params) => {
    if (!params) return;
    // need to use fetch because axios convert blob data to string, and this convertion can corrupt the file
    let response;
    if (params.ids.length === 1) {
      response = await fetch(
        `${getURL("FLOWS", { mode: "download", id: params.ids[0] })}`,
        {
          headers: {
            Accept: "*/*",
          },
        },
      );
    } else {
      response = await fetch(`${getURL("FLOWS", { mode: "download/" })}`, {
        method: "POST",
        body: JSON.stringify(params.ids),
        headers: {
          "Content-Type": "application/json",
          Accept: "application/x-zip-compressed",
        },
      });
    }
    if (!response.ok) {
      throw new Error(`Failed to download flows: ${response.statusText}`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    // Get the filename from the Content-Disposition header
    const contentDisposition = response.headers.get("Content-Disposition");
    let filename = "flows.zip";
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename=(.+)/);
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1].replace(/["']/g, "");
      }
    }

    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
    return {};
  };

  const queryResult = mutate(
    ["useGetDownloadFlowsV2"],
    getDownloadFlowsFn,
    options,
  );

  return queryResult;
};
