import { useFolderStore } from "../../../stores/foldersStore";
import { downloadFlowsFromFolders } from "../services";

export function handleDownloadFolderFn(folderId: string) {
  downloadFlowsFromFolders(folderId).then((data) => {
    const folders = useFolderStore.getState().folders;

    const folder = folders.find((f) => f.id === folderId);

    data.folder_name = folder?.name || "folder";
    data.folder_description = folder?.description || "";

    const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
      JSON.stringify(data),
    )}`;

    const link = document.createElement("a");
    link.href = jsonString;
    link.download = `${data.folder_name}.json`;

    link.click();
  });
}
