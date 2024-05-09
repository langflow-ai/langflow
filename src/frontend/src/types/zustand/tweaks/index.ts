import { tweakType } from "../../components";

export type TweaksStoreType = {
  tweak: tweakType;
  setTweak: (tweak: tweakType) => void;
  tweaksList: string[];
  setTweaksList: (tweaksList: string[]) => void;
};
