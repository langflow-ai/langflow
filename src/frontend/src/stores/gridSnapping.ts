import { create } from "zustand";
import { GridStoreType } from "../types/zustand/grid";

export const useGridSnappingStore = create<GridStoreType>((set, get) => ({
  gridSnapping: JSON.parse(window.localStorage.getItem("isGridSnap")!) ?? false,

  setGridSnapping: (grid) => {
    set(() => ({ gridSnapping: grid }));
    window.localStorage.setItem("isGridSnap", grid.toString());
  },
}));
