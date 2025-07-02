import { AxiosRequestConfig, ResponseType } from "axios";
import { track } from "./analytics";

export const customGetDownloadTypeFolders = (): AxiosRequestConfig => {
  return {
    responseType: "blob" as ResponseType,
    headers: {
      Accept: "application/x-zip-compressed",
    },
  };
};

export const customGetDownloadFolderBlob = (
  response: any,
  id: string,
  folderName?: string,
  setSuccessData?: (data: any) => void,
) => {
  // Create a blob from the response data
  const blob = new Blob([response.data], {
    type: "application/x-zip-compressed",
  });

  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;

  // Get filename from header or use default
  const filename =
    response.headers?.["content-disposition"]
      ?.split("filename=")[1]
      ?.replace(/['"]/g, "") ?? `${folderName || "flows"}.zip`;

  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);

  track("Project Exported", { folderId: id });
};
