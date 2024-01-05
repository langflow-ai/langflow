import { create } from "zustand";
import { FlowsManagerStoreType } from "../types/zustand/flowsManager";

let currentFlowId: string = "";

const useFlowsManagerStore = create<FlowsManagerStoreType>((set, get) => ({
  flows: [],
  currentFlow: get().flows[currentFlowId],
}));

export default useFlowsManagerStore;
