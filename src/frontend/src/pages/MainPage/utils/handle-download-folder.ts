import { downloadFlowsFromFolders } from "../services";

export function handleDownloadFolderFn(folderId: string) {
  downloadFlowsFromFolders(folderId).then((data) => {
    const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
      JSON.stringify(data.flows),
    )}`;

    const link = document.createElement("a");
    link.href = jsonString;
    link.download = `${data.folder_name}.json`;

    link.click();
  });
}
