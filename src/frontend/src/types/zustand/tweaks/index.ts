import { AllNodeType, FlowType } from "@/types/flow";
import { GetCodesType } from "@/types/tweaks";
import { tabsArrayType } from "../../components";

export type TweaksStoreType = {
  activeTweaks: boolean;
  setActiveTweaks: (activeTweaks: boolean) => void;
  nodes: AllNodeType[];
  setNodes: (
    update: AllNodeType[] | ((oldState: AllNodeType[]) => AllNodeType[]),
    skipSave?: boolean,
  ) => void;
  setNode: (
    id: string,
    update: AllNodeType | ((oldState: AllNodeType) => AllNodeType),
  ) => void;
  getCodes: GetCodesType;
  getNode: (id: string) => AllNodeType | undefined;
  tabs: tabsArrayType[];
  initialSetup: (
    autoLogin: boolean,
    flow: FlowType,
    getCodes: GetCodesType,
  ) => void;
  refreshTabs: () => void;
  autoLogin: boolean;
  flow: FlowType | null;
};
