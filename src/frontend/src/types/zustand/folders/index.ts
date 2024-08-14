import { FolderType } from "../../../pages/MainPage/entities";

export type FoldersStoreType = {
  selectedFolder: FolderType | null;
  setSelectedFolder: (folder: FolderType | null) => void;
  getFolderById: (id: string) => void;
  myCollectionFlows: FolderType | null;
  myCollectionId: string | null;
  setMyCollectionId: (value: string) => void;
  folderToEdit: FolderType | null;
  setFolderToEdit: (folder: FolderType | null) => void;
  folderUrl: string;
  setFolderUrl: (folderUrl: string) => void;
  folderDragging: boolean;
  setFolderDragging: (set: boolean) => void;
  folderIdDragging: string;
  setFolderIdDragging: (id: string) => void;
  starterProjectId: string;
  setStarterProjectId: (id: string) => void;
};
