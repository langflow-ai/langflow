import { cloneDeep } from "lodash";
import { create } from "zustand";
import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import type { FlowType } from "../types/flow";
import type {
  FlowsManagerStoreType,
  UseUndoRedoOptions,
} from "../types/zustand/flowsManager";
import useAssistantManagerStore from "./assistantManagerStore";
import useFlowStore from "./flowStore";

const defaultOptions: UseUndoRedoOptions = {
  maxHistorySize: 100,
  enableShortcuts: true,
};

const past = {};
const future = {};

/**
 * ``currentFlow`` is the persisted version of the open flow: the editor diffs
 * the canvas against it, and the unsaved-changes dialog reads its
 * ``updated_at`` for the "Last saved" line.
 *
 * The refreshed list is not always that shape. The app header polls
 * ``GET /flows/?get_all=true&header_flows=true``, whose rows are ``FlowHeader``
 * objects — they carry no ``updated_at`` at all, and ``data`` is nulled for
 * anything that is not a component. Taking such a row wholesale blanks both,
 * which is what made the exit dialog claim "Last saved: Never" for a flow that
 * was in fact persisted. Apply what the refreshed row knows, keep what only the
 * full flow can tell us.
 */
const mergeRefreshedCurrentFlow = (
  saved: FlowType | undefined,
  refreshed: FlowType | undefined,
): FlowType | undefined => {
  if (!refreshed) return undefined;
  if (!saved || saved.id !== refreshed.id) return refreshed;
  return {
    ...saved,
    ...refreshed,
    data: refreshed.data ?? saved.data,
    updated_at: refreshed.updated_at ?? saved.updated_at,
  };
};

const useFlowsManagerStore = create<FlowsManagerStoreType>((set, get) => ({
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
    // Close assistant when changing flows
    useAssistantManagerStore.getState().setAssistantSidebarOpen(false);
  },
  getFlowById: (id: string) => {
    return get().flows?.find((flow) => flow.id === id);
  },
  flows: undefined,
  setFlows: (flows: FlowType[]) => {
    set({
      flows,
      currentFlow: mergeRefreshedCurrentFlow(
        get().currentFlow,
        flows.find((flow) => flow.id === get().currentFlowId),
      ),
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
      flows: undefined,
      currentFlow: undefined,
      currentFlowId: "",
      searchFlowsComponents: "",
      selectedFlowsComponentsCards: [],
    });
  },
}));

export default useFlowsManagerStore;
