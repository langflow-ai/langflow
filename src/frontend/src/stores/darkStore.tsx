import { create } from "zustand";
import { getRepoStars, getVersion } from "../controllers/API";
import { DarkStoreType } from "../types/zustand/dark";

export const useDarkStore = create<DarkStoreType>((set) => ({
  dark: JSON.parse(window.localStorage.getItem("isDark")!) ?? false,
  stars: 0,
  version: "",
  setDark: (dark) => set(() => ({ dark: dark })),
  refreshVersion: () => {
    getVersion().then((data) => {
      set(() => ({ version: data.version }));
    });
  },
  refreshStars: () => {
    getRepoStars("logspace-ai", "langflow").then((res) => {
      set(() => ({ stars: res }));
    });
  },
}));
