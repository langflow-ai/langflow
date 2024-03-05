import { create } from "zustand";
import { getRepoStars, getVersion } from "../controllers/API";
import { DarkStoreType } from "../types/zustand/dark";

const startedStars = Number(window.localStorage.getItem("githubStars")) ?? 0;

export const useDarkStore = create<DarkStoreType>((set) => ({
  dark: JSON.parse(window.localStorage.getItem("isDark")!) ?? false,
  stars: startedStars,
  version: "",
  setDark: (dark) => set(() => ({ dark: dark })),
  refreshVersion: () => {
    getVersion().then((data) => {
      set(() => ({ version: data.version }));
    });
  },
  refreshStars: () => {
    if (window.localStorage.getItem("githubStars") !== null) {
      set(() => ({ stars: startedStars }));
      return;
    }

    getRepoStars("logspace-ai", "langflow").then((res) => {
      window.localStorage.setItem("githubStars", res.toString());
      set(() => ({ stars: res }));
    });
  },
}));
