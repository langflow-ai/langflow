import { tweakType } from "../../components";

export type TweaksStoreType = {
  tweaksObject: tweakType;
  setTweaksObject: (tweak: tweakType) => void;
  tweak: tweakType;
  setTweak: (tweak: tweakType) => void;
  tweaksList: string[];
  setTweaksList: (tweaksList: string[]) => void;
};
