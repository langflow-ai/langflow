import { FlowType } from "@/types/flow";

export const customDownloadFlow = (
  flow: FlowType,
  sortedJsonString: string,
  flowName: string,
) => {
  const dataUri = `data:text/json;chatset=utf-8,${encodeURIComponent(sortedJsonString)}`;
  const downloadLink = document.createElement("a");
  downloadLink.href = dataUri;
  downloadLink.download = `${flowName || flow.name}.json`;

  downloadLink.click();
};
