import { getFetchCredentials } from "@/customization/utils/get-fetch-credentials";
import type { FlowType } from "@/types/flow";
import { downloadFlow, processFlows } from "@/utils/reactflowUtils";
import type { useMutationFunctionType } from "../../../../types/api";
import { api } from "../../api";
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
      response = await api.get<FlowType>(`${getURL("FLOWS")}/${params.ids[0]}`);

      const flowsArrayToProcess = [response.data];
      const { flows } = processFlows(flowsArrayToProcess);

      const flow = flows[0];
      if (flow) {
        downloadFlow(flow, flow.name, flow.description);
      }
    } else {
      response = await fetch(`${getURL("FLOWS", { mode: "download/" })}`, {
        method: "POST",
        body: JSON.stringify(params.ids),
        headers: {
          "Content-Type": "application/json",
          Accept: "application/x-zip-compressed",
        },
        credentials: getFetchCredentials(),
      });
      if (!response.ok) {
        throw new Error(`Failed to download flows: ${response.statusText}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      // Get the filename from the Content-Disposition header (RFC 5987: filename*=UTF-8''<encoded>)
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = "flows.zip";
      if (contentDisposition) {
        const rfc5987Match = contentDisposition.match(
          /filename\*=UTF-8''([^;]+)/i,
        );
        if (rfc5987Match && rfc5987Match[1]) {
          filename = decodeURIComponent(rfc5987Match[1].trim());
        } else {
          const filenameMatch = contentDisposition.match(
            /filename="?([^";\n]+)"?/,
          );
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1].trim();
          }
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
    }
  };

  const queryResult = mutate(
    ["useGetDownloadFlowsV2"],
    getDownloadFlowsFn,
    options,
  );

  return queryResult;
};
