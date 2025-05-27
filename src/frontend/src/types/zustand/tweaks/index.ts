import { AllNodeType } from "@/types/flow";

export type TweaksStoreType = {
  nodes: AllNodeType[];
  setNodes: (
    update: AllNodeType[] | ((oldState: AllNodeType[]) => AllNodeType[]),
    skipSave?: boolean,
  ) => void;
  setNode: (
    id: string,
    update: AllNodeType | ((oldState: AllNodeType) => AllNodeType),
  ) => void;
  getNode: (id: string) => AllNodeType | undefined;
  newInitialSetup: (nodes: AllNodeType[]) => void;
  updateTweaks: () => void;
  tweaks: {
    [key: string]: {
      [key: string]: any;
    };
  };
};
