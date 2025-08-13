import type { AllNodeType } from "@/types/flow";

export type TweaksStoreType = {
  nodes: AllNodeType[];
  currentFlowId: string;
  setNodes: (
    update: AllNodeType[] | ((oldState: AllNodeType[]) => AllNodeType[]),
    skipSave?: boolean,
  ) => void;
  setNode: (
    id: string,
    update: AllNodeType | ((oldState: AllNodeType) => AllNodeType),
  ) => void;
  getNode: (id: string) => AllNodeType | undefined;
  initialSetup: (nodes: AllNodeType[], flowId: string) => void;
  updateTweaks: () => void;
  tweaks: {
    [key: string]: {
      [key: string]: any;
    };
  };
};
