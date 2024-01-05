import { create } from "zustand";
import { FlowsContextType } from "../types/tabs";
import { FlowsManagerStoreType } from "../types/zustand/flowsManager";
  
const useFlowStore = create<FlowsManagerStoreType>((set, get) => ({
    flows: [],
}));

export default useFlowStore;