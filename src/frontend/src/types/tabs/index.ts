import { FlowType } from "../flow";

export type TabsContextType = {
  save: () => void;
  tabIndex: number;
  setTabIndex: (index: number) => void;
  flows: Array<FlowType>;
  removeFlow: (id: string) => void;
  addFlow: (flowData?: FlowType) => void;
  updateFlow: (newFlow: FlowType) => void;
  incrementNodeId: () => number;
  downloadFlow: (flow: FlowType) => void;
  uploadFlow: () => void;
  hardReset: () => void;
};

export type LangFlowState={ tabIndex:number, flows:FlowType[], id:string, nodeId:number }