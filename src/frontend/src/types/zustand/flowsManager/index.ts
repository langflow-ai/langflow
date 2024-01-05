import { FlowType } from "../../flow";

export type FlowsManagerStoreType = {
  flows: Array<FlowType>;
  currentFlow: FlowType | undefined;
};
