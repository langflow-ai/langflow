import type { FolderType } from "@/pages/MainPage/entities";

export const handleSelectChange = (
  option: string,
  folder: FolderType,
  handleDeleteFolder: ((folder: FolderType) => void) | undefined,
  handleDownloadFolder: (folderId: string) => void,
  handleSelectFolderToRename: (folder: FolderType) => void,
) => {
  switch (option) {
    case "delete":
      handleDeleteFolder!(folder);
      break;
    case "download":
      handleDownloadFolder(folder.id!);
      break;
    case "rename":
      handleSelectFolderToRename(folder);
      break;
  }
};
