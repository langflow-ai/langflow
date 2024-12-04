import { FlowType } from "@/types/flow";
import { FolderType } from "../../../pages/MainPage/entities";

export type FoldersStoreType = {
  myCollectionId: string | null;
  setMyCollectionId: (value: string) => void;
  folderToEdit: FolderType | null;
  setFolderToEdit: (folder: FolderType | null) => void;
  folderDragging: boolean;
  setFolderDragging: (set: boolean) => void;
  folderIdDragging: string;
  setFolderIdDragging: (id: string) => void;
  starterProjectId: string;
  setStarterProjectId: (id: string) => void;
  folders: FolderType[];
  setFolders: (folders: FolderType[]) => void;
};
