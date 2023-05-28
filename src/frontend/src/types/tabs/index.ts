import { FlowType } from "../flow";

export type TabsContextType = {
  save: () => void;
  tabIndex: number;
  setTabIndex: (index: number) => void;
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
    position: { x: number; y: number }
  ) => void;
};

export type LangFlowState = {
  tabIndex: number;
  flows: FlowType[];
  id: string;
  nodeId: number;
};
