import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import { cloneDeep } from "lodash";
import { create } from "zustand";
import { FlowType } from "../types/flow";
import {
  FlowsManagerStoreType,
  UseUndoRedoOptions,
} from "../types/zustand/flowsManager";
import useFlowStore from "./flowStore";

const defaultOptions: UseUndoRedoOptions = {
  maxHistorySize: 100,
  enableShortcuts: true,
};

const past = {};
const future = {};

const useFlowsManagerStore = create<FlowsManagerStoreType>((set, get) => ({
  voiceModeEnabled: false,
  setVoiceModeEnabled: (voiceModeEnabled: boolean) => set({ voiceModeEnabled }),
  IOModalOpen: false,
  setIOModalOpen: (IOModalOpen: boolean) => {
    set({ IOModalOpen });
  },
  healthCheckMaxRetries: 5,
  setHealthCheckMaxRetries: (healthCheckMaxRetries: number) =>
    set({ healthCheckMaxRetries }),
  autoSaving: true,
  setAutoSaving: (autoSaving: boolean) => set({ autoSaving }),
  autoSavingInterval: SAVE_DEBOUNCE_TIME,
  setAutoSavingInterval: (autoSavingInterval: number) =>
    set({ autoSavingInterval }),
  examples: [],
  setExamples: (examples: FlowType[]) => {
    set({ examples });
  },
  currentFlowId: "",
  setCurrentFlow: (flow: FlowType | undefined) => {
    set({
      currentFlow: flow,
      currentFlowId: flow?.id ?? "",
    });
    useFlowStore.getState().resetFlow(flow);
  },
  getFlowById: (id: string) => {
    return get().flows?.find((flow) => flow.id === id);
  },
  flows: undefined,
  setFlows: (flows: FlowType[]) => {
    set({
      flows,
      currentFlow: flows.find((flow) => flow.id === get().currentFlowId),
    });
  },
  currentFlow: undefined,
  saveLoading: false,
  setSaveLoading: (saveLoading: boolean) => set({ saveLoading }),
  isLoading: false,
  setIsLoading: (isLoading: boolean) => set({ isLoading }),
  takeSnapshot: () => {
    const currentFlowId = get().currentFlowId;
    // push the current graph to the past state
    const flowStore = useFlowStore.getState();
    const newState = {
      nodes: cloneDeep(flowStore.nodes),
      edges: cloneDeep(flowStore.edges),
    };
    const pastLength = past[currentFlowId]?.length ?? 0;
    if (
      pastLength > 0 &&
      JSON.stringify(past[currentFlowId][pastLength - 1]) ===
        JSON.stringify(newState)
    )
      return;
    if (pastLength > 0) {
      past[currentFlowId] = past[currentFlowId].slice(
        pastLength - defaultOptions.maxHistorySize + 1,
        pastLength,
      );

      past[currentFlowId].push(newState);
    } else {
      past[currentFlowId] = [newState];
    }

    future[currentFlowId] = [];
  },
  undo: () => {
    const newState = useFlowStore.getState();
    const currentFlowId = get().currentFlowId;
    const pastLength = past[currentFlowId]?.length ?? 0;
    const pastState = past[currentFlowId]?.[pastLength - 1] ?? null;

    if (pastState) {
      past[currentFlowId] = past[currentFlowId].slice(0, pastLength - 1);

      if (!future[currentFlowId]) future[currentFlowId] = [];
      future[currentFlowId].push({
        nodes: newState.nodes,
        edges: newState.edges,
      });

      newState.setNodes(pastState.nodes);
      newState.setEdges(pastState.edges);
    }
  },
  redo: () => {
    const newState = useFlowStore.getState();
    const currentFlowId = get().currentFlowId;
    const futureLength = future[currentFlowId]?.length ?? 0;
    const futureState = future[currentFlowId]?.[futureLength - 1] ?? null;

    if (futureState) {
      future[currentFlowId] = future[currentFlowId].slice(0, futureLength - 1);

      if (!past[currentFlowId]) past[currentFlowId] = [];
      past[currentFlowId].push({
        nodes: newState.nodes,
        edges: newState.edges,
      });

      newState.setNodes(futureState.nodes);
      newState.setEdges(futureState.edges);
    }
  },
  searchFlowsComponents: "",
  setSearchFlowsComponents: (searchFlowsComponents: string) => {
    set({ searchFlowsComponents });
  },
  selectedFlowsComponentsCards: [],
  setSelectedFlowsComponentsCards: (selectedFlowsComponentsCards: string[]) => {
    set({ selectedFlowsComponentsCards });
  },
  resetStore: () => {
    set({
      flows: [],
      currentFlow: undefined,
      currentFlowId: "",
      searchFlowsComponents: "",
      selectedFlowsComponentsCards: [],
    });
  },
}));

export default useFlowsManagerStore;
