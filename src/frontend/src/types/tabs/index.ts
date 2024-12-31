import { XYPosition } from "@xyflow/react";
import { FlowType, NodeDataType } from "../flow";

type OnChange<ChangesType> = (changes: ChangesType[]) => void;

export type FlowsContextType = {
  //keep
  saveFlow: (flow?: FlowType, silent?: boolean) => Promise<void>;
  tabId: string;
  //keep
  isLoading: boolean;
  setTabId: (index: string) => void;
  //keep
  removeFlow: (id: string) => void;
  refreshFlows: () => void;
  //keep
  addFlow: (
    newProject: boolean,
    flow?: FlowType,
    override?: boolean,
    position?: XYPosition,
  ) => Promise<String | undefined>;
  downloadFlow: (
    flow: FlowType,
    flowName: string,
    flowDescription?: string,
  ) => void;
  //keep
  downloadFlows: () => void;
  //keep
  uploadFlows: () => void;
  setVersion: (version: string) => void;
  uploadFlow: ({
    newProject,
    file,
    isComponent,
    position,
  }: {
    newProject: boolean;
    file?: File;
    isComponent?: boolean;
    position?: XYPosition;
  }) => Promise<String | never>;
  tabsState: FlowsState;
  setTabsState: (
    update: FlowsState | ((oldState: FlowsState) => FlowsState),
  ) => void;
  saveComponent: (
    component: NodeDataType,
    override: boolean,
  ) => Promise<String | undefined>;
  deleteComponent: (key: string) => void;
  version: string;
  flows: Array<FlowType>;
};

export type FlowsState = {
  [key: string]: FlowState | undefined;
};

export type FlowState = {
  template?: string;
  input_keys?: Object;
  memory_keys?: Array<string>;
  handle_keys?: Array<string>;
};

export type errorsVarType = {
  title: string;
  list?: Array<string>;
};
