import { create } from "zustand";
import { TweaksStoreType } from "../types/zustand/tweaks";

export const useTweaksStore = create<TweaksStoreType>((set, get) => ({
  tweak: [],
  setTweak: (tweak) => set({ tweak }),
  tweaksList: [],
  setTweaksList: (tweaksList) => set({ tweaksList }),
}));
