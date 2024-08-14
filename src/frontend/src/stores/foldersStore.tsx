import { create } from "zustand";
import { FoldersStoreType } from "../types/zustand/folders";

export const useFolderStore = create<FoldersStoreType>((set, get) => ({
  selectedFolder: null,
  setSelectedFolder: (folder) => set(() => ({ selectedFolder: folder })),
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
}));
