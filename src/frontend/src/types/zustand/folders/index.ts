import { FolderType } from "../../../pages/MainPage/entities";

export type FoldersStoreType = {
  folders: FolderType[];
  getFoldersApi: (refetch?: boolean) => Promise<void>;
  setFolders: (folders: FolderType[]) => void;
  loading: boolean;
  setLoading: (loading: boolean) => void;
  selectedFolder: FolderType | null;
  getFolderById: (id: string) => void;
  loadingById: boolean;
  setLoadingById: (loading: boolean) => void;
  getMyCollectionFolder: () => void;
  myCollectionFlows: FolderType | null;
  myCollectionId: string | null;
  setMyCollectionId: () => void;
  folderToEdit: FolderType | null;
  setFolderToEdit: (folder: FolderType | null) => void;
  folderUrl: string;
  setFolderUrl: (folderUrl: string) => void;
  folderDragging: boolean;
  setFolderDragging: (set: boolean) => void;
  uploadFolder: (folderId: string) => Promise<void>;
  folderIdDragging: string;
  setFolderIdDragging: (id: string) => void;
  starterProjectId: string;
  setStarterProjectId: (id: string) => void;
};
