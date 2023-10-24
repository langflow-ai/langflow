import { FlowType } from "../flow";

export type storeContextType = {
  savedFlows: { [key: string]: FlowType };
  setSavedFlows: (newState: { [key: string]: FlowType }) => void;
};
