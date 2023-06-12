import { FlowType } from "../flow";

export type TabsContextType = {
  tabId: string;
  setTabId: (index: string) => void;
  flows: Array<FlowType>;
  removeFlow: (id: string) => void;
  addFlow: (flowData?: FlowType, newFlow?: boolean) => void;
  updateFlow: (newFlow: FlowType) => void;
  incrementNodeId: () => string;
  downloadFlow: (flow: FlowType) => void;
  uploadFlow: (newFlow?: boolean) => void;
  hardReset: () => void;
  //disable CopyPaste
  disableCopyPaste: boolean;
  setDisableCopyPaste: (value: boolean) => void;
  getNodeId: () => string;
  paste: (
    selection: { nodes: any; edges: any },
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) => void;
  lastCopiedSelection: { nodes: any; edges: any };
  setLastCopiedSelection: (selection: { nodes: any; edges: any }) => void;
};

export type LangFlowState = {
  tabIndex: number;
  flows: FlowType[];
  id: string;
  nodeId: number;
};
