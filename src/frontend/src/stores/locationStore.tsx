import { create } from "zustand";
import { LocationStoreType } from "../types/zustand/location";

export const useLocationStore = create<LocationStoreType>((set, get) => ({
  current: window.location.pathname.replace(/\/$/g, "").split("/"),
  isStackedOpen:
    window.innerWidth > 1024 && window.location.pathname.split("/")[1]
      ? true
      : false,
  setCurrent: (newState) => {
    set({ current: newState });
  },
}));
