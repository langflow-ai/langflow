import { FlowType, NodeType } from "@/types/flow";
import { tabsArrayType } from "../../components";

export type TweaksStoreType = {
  activeTweaks: boolean;
  setActiveTweaks: (activeTweaks: boolean) => void;
  nodes: NodeType[];
  setNodes: (
    update: NodeType[] | ((oldState: NodeType[]) => NodeType[]),
    skipSave?: boolean,
  ) => void;
  setNode: (
    id: string,
    update: NodeType | ((oldState: NodeType) => NodeType),
  ) => void;
  getNode: (id: string) => NodeType | undefined;
  tabs: tabsArrayType[];
  initialSetup: (autoLogin: boolean, flow: FlowType) => void;
  refreshTabs: () => void;
  autoLogin: boolean;
  flow: FlowType | null;
};
