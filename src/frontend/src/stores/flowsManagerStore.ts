import { create } from "zustand";
import { FlowsManagerStoreType } from "../types/zustand/flowsManager";
import { FlowState } from "../types/tabs";

const useFlowsManagerStore = create<FlowsManagerStoreType>((set, get) => ({
  currentFlowId: "",
  flows: [],
  currentFlow: get().flows[get().currentFlowId],
  isLoading: true,
  setIsLoading: (isLoading: boolean) => set({ isLoading }),
  flowsState: {},
  currentFlowState: get().flowsState[get().currentFlowId],
  setCurrentFlowState: (flowState: FlowState | ((oldState: FlowState) => FlowState)) => {
    const newFlowState = typeof flowState === "function" ? flowState(get().currentFlowState) : flowState;
    set((state) => ({
      flowsState: {
        ...state.flowsState,
        [state.currentFlowId]: newFlowState,
      },
    }));
  },

}));

export default useFlowsManagerStore;
