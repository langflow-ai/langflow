import { downloadFlowsFromFolders } from "../services";

export const handleDownloadFolderFn = (folderId) => {
  downloadFlowsFromFolders(folderId).then((flows) => {
    const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
      JSON.stringify(flows),
    )}`;

    const link = document.createElement("a");
    link.href = jsonString;
    link.download = `flows.json`;

    link.click();
  });
};
