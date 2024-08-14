import { create } from "zustand";
import { getFolderById } from "../pages/MainPage/services";
import { FoldersStoreType } from "../types/zustand/folders";
import useFlowsManagerStore from "./flowsManagerStore";

export const useFolderStore = create<FoldersStoreType>((set, get) => ({
  getFolderById: (id) => {
    if (id) {
      getFolderById(id).then((res) => {
        const setAllFlows = useFlowsManagerStore.getState().setAllFlows;
        setAllFlows(res?.flows);
        set({ selectedFolder: res });
      });
    }
  },
  selectedFolder: null,
  setSelectedFolder: (folder) => set(() => ({ selectedFolder: folder })),
  loadingById: false,
  setMyCollectionFlow: (folder) => set(() => ({ myCollectionFlows: folder })),
  myCollectionFlows: null,
  setMyCollectionId: (myCollectionId) => {
    set({ myCollectionId });
  },
  myCollectionId: "",
  folderToEdit: null,
  setFolderToEdit: (folder) => set(() => ({ folderToEdit: folder })),
  folderUrl: "",
  setFolderUrl: (url) => set(() => ({ folderUrl: url })),
  folderDragging: false,
  setFolderDragging: (folder) => set(() => ({ folderDragging: folder })),
  folderIdDragging: "",
  setFolderIdDragging: (id) => set(() => ({ folderIdDragging: id })),
  starterProjectId: "",
  setStarterProjectId: (id) => set(() => ({ starterProjectId: id })),
}));
