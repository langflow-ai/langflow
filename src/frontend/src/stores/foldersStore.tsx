import { create } from "zustand";
import { DEFAULT_FOLDER, STARTER_FOLDER_NAME } from "../constants/constants";
import {
  getFolderById,
  getFolders,
  uploadFlowsFromFolders,
} from "../pages/MainPage/services";
import { FoldersStoreType } from "../types/zustand/folders";
import useFlowsManagerStore from "./flowsManagerStore";

export const useFolderStore = create<FoldersStoreType>((set, get) => ({
  folders: [],
  getFoldersApi: (refetch = false) => {
    return new Promise<void>((resolve, reject) => {
      if (get()?.folders.length === 0 || refetch === true) {
        get().setLoading(true);
        getFolders().then(
          (res) => {
            const foldersWithoutStarterProjects = res.filter(
              (folder) => folder.name !== STARTER_FOLDER_NAME,
            );

            const starterProjects = res.find(
              (folder) => folder.name === STARTER_FOLDER_NAME,
            );

            set({ starterProjectId: starterProjects!.id ?? "" });
            set({ folders: foldersWithoutStarterProjects });

            const myCollectionId = res?.find(
              (f) => f.name === DEFAULT_FOLDER,
            )?.id;

            set({ myCollectionId });

            if (refetch === true) {
              useFlowsManagerStore.getState().refreshFlows();
              useFlowsManagerStore.getState().setAllFlows;
            }

            get().setLoading(false);
            resolve();
          },
          (error) => {
            set({ folders: [] });
            get().setLoading(false);
            reject(error);
          },
        );
      }
    });
  },
  setFolders: (folders) => set(() => ({ folders: folders })),
  loading: false,
  setLoading: (loading) => set(() => ({ loading: loading })),
  getFolderById: (id) => {
    get().setLoadingById(true);
    if (id) {
      getFolderById(id).then(
        (res) => {
          const setAllFlows = useFlowsManagerStore.getState().setAllFlows;
          setAllFlows(res.flows);
          set({ selectedFolder: res });
          get().setLoadingById(false);
        },
        () => {
          get().setLoadingById(false);
        },
      );
    }
  },
  selectedFolder: null,
  loadingById: false,
  setLoadingById: (loading) => set(() => ({ loadingById: loading })),
  getMyCollectionFolder: () => {
    const folders = get().folders;
    const myCollectionId = folders?.find((f) => f.name === DEFAULT_FOLDER)?.id;
    if (myCollectionId) {
      getFolderById(myCollectionId).then((res) => {
        set({ myCollectionFlows: res });
      });
    }
  },
  setMyCollectionFlow: (folder) => set(() => ({ myCollectionFlows: folder })),
  myCollectionFlows: null,
  setMyCollectionId: () => {
    const folders = get().folders;
    const myCollectionId = folders?.find((f) => f.name === DEFAULT_FOLDER)?.id;
    if (myCollectionId) {
      set({ myCollectionId });
    }
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
  uploadFolder: () => {
    return new Promise<void>((resolve, reject) => {
      const input = document.createElement("input");
      input.type = "file";
      input.onchange = (event: Event) => {
        if (
          (event.target as HTMLInputElement).files![0].type ===
          "application/json"
        ) {
          const file = (event.target as HTMLInputElement).files![0];
          const formData = new FormData();
          formData.append("file", file);
          file.text().then((text) => {
            const data = JSON.parse(text);
            if (data.data?.nodes) {
              useFlowsManagerStore
                .getState()
                .addFlow(true, data)
                .then(() => {
                  resolve();
                })
                .catch((error) => {
                  reject(error);
                });
            } else {
              uploadFlowsFromFolders(formData)
                .then(() => {
                  get()
                    .getFoldersApi(true)
                    .then(() => {
                      resolve();
                    });
                })
                .catch((error) => {
                  reject(error);
                });
            }
          });
        }
      };
      input.click();
    });
  },
  starterProjectId: "",
  setStarterProjectId: (id) => set(() => ({ starterProjectId: id })),
}));
