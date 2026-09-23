import type { AxiosRequestConfig, AxiosResponse, ResponseType } from "axios";
import type { AlertStoreType } from "@/types/zustand/alert";
import { parseContentDispositionFilename } from "@/utils/parse-content-disposition-filename";
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
  response: AxiosResponse<Blob>,
  id: string,
  folderName?: string,
  setSuccessData?: AlertStoreType["setSuccessData"],
) => {
  // Create a blob from the response data
  const blob = new Blob([response.data], {
    type: "application/x-zip-compressed",
  });

  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;

  // Prefer the RFC 5987 filename* param so non-ASCII project names survive
  const header = response.headers?.["content-disposition"];
  const filename = parseContentDispositionFilename(
    typeof header === "string" ? header : null,
    `${folderName || "flows"}.zip`,
  );

  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);

  track("Project Exported", { folderId: id });
};
