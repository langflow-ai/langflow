import { create } from "zustand";
import type { FoldersStoreType } from "../types/zustand/folders";

export const useFolderStore = create<FoldersStoreType>((set, get) => ({
  loadingById: false,
  setMyCollectionId: (myCollectionId) => {
    set({ myCollectionId });
  },
  myCollectionId: "",
  folderToEdit: null,
  setFolderToEdit: (folder) => set(() => ({ folderToEdit: folder })),
  folderDragging: false,
  setFolderDragging: (folder) => set(() => ({ folderDragging: folder })),
  folderIdDragging: "",
  setFolderIdDragging: (id) => set(() => ({ folderIdDragging: id })),
  starterProjectId: "",
  setStarterProjectId: (id) => set(() => ({ starterProjectId: id })),
  folders: [],
  setFolders: (folders) => set(() => ({ folders: folders })),
  resetStore: () => {
    set({
      folders: [],
      myCollectionId: "",
      folderToEdit: null,
      folderDragging: false,
      folderIdDragging: "",
    });
  },
}));
