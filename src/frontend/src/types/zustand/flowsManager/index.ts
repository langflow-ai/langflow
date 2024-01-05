import { XYPosition } from "reactflow";
import { FlowType, NodeDataType } from "../../flow";
import { FlowsState } from "../../tabs";

export type FlowsManagerStoreType = {
    flows: Array<FlowType>;
    currentFlow: FlowType | undefined;
  };