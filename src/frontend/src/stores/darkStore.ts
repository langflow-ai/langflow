import { create } from "zustand";
import { getDiscordCount, getRepoStars } from "../controllers/API";
import type { DarkStoreType } from "../types/zustand/dark";

const startedStars = Number(window.localStorage.getItem("githubStars")) ?? 0;

export const useDarkStore = create<DarkStoreType>((set, get) => ({
  dark: (() => {
    const stored = window.localStorage.getItem("isDark");
    return stored !== null ? JSON.parse(stored) : false;
  })(),
  stars: startedStars,
  version: "",
  latestVersion: "",
  refreshLatestVersion: (v: string) => {
    set(() => ({ latestVersion: v }));
  },
  setDark: (dark) => {
    set(() => ({ dark: dark }));
    window.localStorage.setItem("isDark", dark.toString());
  },
  refreshVersion: (v) => {
    set(() => ({ version: v }));
  },
  refreshStars: () => {
    if (import.meta.env.CI) {
      window.localStorage.setItem("githubStars", "0");
      set(() => ({ stars: 0, lastUpdated: new Date() }));
      return;
    }
    const lastUpdated = window.localStorage.getItem("githubStarsLastUpdated");
    let diff = 0;
    // check if lastUpdated actually exists
    if (lastUpdated !== null) {
      diff = Math.abs(new Date().getTime() - new Date(lastUpdated).getTime());
    }

    // if lastUpdated is null or the difference is greater than 2 hours
    if (lastUpdated === null || diff > 7200000) {
      getRepoStars("langflow-ai", "langflow").then((res) => {
        window.localStorage.setItem("githubStars", res?.toString() ?? "0");
        window.localStorage.setItem(
          "githubStarsLastUpdated",
          new Date().toString(),
        );
        set(() => ({ stars: res, lastUpdated: new Date() }));
      });
    }
  },
  discordCount: 0,
  refreshDiscordCount: () => {
    getDiscordCount().then((res) => {
      set(() => ({ discordCount: res }));
    });
  },
}));
