import { create } from "zustand";
import { getRepoStars } from "../controllers/API";
import { DarkStoreType } from "../types/zustand/dark";

function gradientIndexInitialState() {
  const min = 0;
  const max = 30;
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

export const useDarkStore = create<DarkStoreType>((set) => ({
  dark: JSON.parse(window.localStorage.getItem("isDark")!) ?? false,
  stars: 0,
  gradientIndex: gradientIndexInitialState(),
  setDark: (dark) => set(() => ({ dark: dark })),
  setStars: (starts) => set(() => ({ stars: starts })),
  setGradientIndex: (gradientIndex) =>
    set(() => ({ gradientIndex: gradientIndex })),
}));

getRepoStars("logspace-ai", "langflow").then((res) => {
  useDarkStore.setState({ stars: res });
});
