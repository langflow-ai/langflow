import { create } from "zustand";
import { tweakType } from "../types/components";
import { TweaksStoreType } from "../types/zustand/tweaks";

export const useTweaksStore = create<TweaksStoreType>((set, get) => ({
  tweaksObject: [{}],
  setTweaksObject: (tweak: tweakType) => {
    tweak.forEach((el) => {
      Object.keys(el).forEach((key) => {
        for (let kp in el[key]) {
          try {
            el[key][kp] = JSON.parse(el[key][kp]);
          } catch {}
        }
      });
    });
    set({ tweaksObject: tweak });
  },
  tweak: [],
  setTweak: (tweak) => set({ tweak }),
  tweaksList: [],
  setTweaksList: (tweaksList) => set({ tweaksList }),
}));
