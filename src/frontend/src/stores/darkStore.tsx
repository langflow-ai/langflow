import { create } from "zustand";
import { getRepoStars, getVersion } from "../controllers/API";
import { DarkStoreType } from "../types/zustand/dark";

const startedStars = Number(window.localStorage.getItem("githubStars")) ?? 0;

export const useDarkStore = create<DarkStoreType>((set, get) => ({
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
    let lastUpdated = window.localStorage.getItem("githubStarsLastUpdated");
    let diff = 0;
    // check if lastUpdated actually exists
    if (lastUpdated !== null) {
      diff = Math.abs(new Date().getTime() - new Date(lastUpdated).getTime());
    }

    // if lastUpdated is null or the difference is greater than 2 hours
    if (lastUpdated === null || diff > 7200000) {
      getRepoStars("logspace-ai", "langflow").then((res) => {
        window.localStorage.setItem("githubStars", res.toString());
        window.localStorage.setItem(
          "githubStarsLastUpdated",
          new Date().toString()
        );
        set(() => ({ stars: res, lastUpdated: new Date() }));
      });
    }
  },
}));
