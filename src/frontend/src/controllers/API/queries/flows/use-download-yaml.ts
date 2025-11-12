import type { useMutationFunctionType } from "../../../../types/api";
import { BASE_URL_API } from "../../../../constants/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DownloadYamlParams {
  flowId: string;
}

export const useDownloadYaml: useMutationFunctionType<
  undefined,
  DownloadYamlParams
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const downloadYamlFn = async (params: DownloadYamlParams | undefined) => {
    if (!params?.flowId) {
      throw new Error("Flow ID is required");
    }

    // Use fetch because axios can corrupt blob data
    const response = await fetch(
      `${BASE_URL_API}spec-builder/download-yaml/${params.flowId}`,
      {
        method: "GET",
        headers: {
          Accept: "application/x-yaml",
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to download YAML: ${response.statusText}`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    // Get the filename from the Content-Disposition header
    const contentDisposition = response.headers.get("Content-Disposition");
    let filename = "flow.yaml";
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename=(.+)/);
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1].replace(/["']/g, "");
      }
    }

    // Create download link and trigger download
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // Clean up
    URL.revokeObjectURL(url);

    return {};
  };

  const queryResult = mutate(
    ["useDownloadYaml"],
    downloadYamlFn,
    options,
  );

  return queryResult;
};
