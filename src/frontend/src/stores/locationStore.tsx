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
  setIsStackedOpen: (newState) => {
    set({ isStackedOpen: newState });
  },
  showSideBar: window.location.pathname.split("/")[1] ? true : false,
  setShowSideBar: (newState) => {
    set({ showSideBar: newState });
  },
  extraNavigation: { title: "" },
  setExtraNavigation: (newState) => {
    set({ extraNavigation: newState });
  },
  extraComponent: <></>,
  setExtraComponent: (newState) => {
    set({ extraComponent: newState });
  },
}));
