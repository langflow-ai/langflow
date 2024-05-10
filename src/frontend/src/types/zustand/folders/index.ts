import { FolderType } from "../../../pages/MainPage/entities";

export type FoldersStoreType = {
  folders: FolderType[];
  getFoldersApi: () => void;
  setFolders: (folders: FolderType[]) => void;
  loading: boolean;
  setLoading: (loading: boolean) => void;
  selectedFolder: FolderType[];
  getFolderById: (id: string) => void;
  loadingById: boolean;
  setLoadingById: (loading: boolean) => void;
};
