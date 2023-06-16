import { Dispatch, SetStateAction } from "react";
import { FlowType } from "../flow";

export type TabsContextType = {
  saveFlow: (flow: FlowType) => Promise<void>;
  save: () => void;
  tabId: string;
  setTabId: (index: string) => void;
  flows: Array<FlowType>;
  removeFlow: (id: string) => void;
  addFlow: (flowData?: FlowType, newProject?: boolean) => Promise<String>;
  updateFlow: (newFlow: FlowType) => void;
  incrementNodeId: () => string;
  downloadFlow: (flow: FlowType) => void;
  downloadFlows: () => void;
  uploadFlows: () => void;
  uploadFlow: (newFlow?: boolean) => void;
  hardReset: () => void;
  //disable CopyPaste
  disableCopyPaste: boolean;
  setDisableCopyPaste: (value: boolean) => void;
  getNodeId: (nodeType: string) => string;
  tabsState: TabsState;
  setTabsState: Dispatch<SetStateAction<TabsState>>;
  paste: (
    selection: { nodes: any; edges: any },
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) => void;
  lastCopiedSelection: { nodes: any; edges: any };
  setLastCopiedSelection: (selection: { nodes: any; edges: any }) => void;
};

export type TabsState = {
  [key: string]: {
    isPending: boolean;
  };
};
