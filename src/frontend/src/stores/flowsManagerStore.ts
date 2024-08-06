import { AxiosError } from "axios";
import { cloneDeep } from "lodash";
import pDebounce from "p-debounce";
import { Edge, Node, Viewport } from "reactflow";
import { create } from "zustand";
import { SAVE_DEBOUNCE_TIME } from "../constants/constants";
import {
  deleteFlowFromDatabase,
  multipleDeleteFlowsComponents,
  readFlowsFromDatabase,
  updateFlowInDatabase,
} from "../controllers/API";
import { FlowType } from "../types/flow";
import {
  FlowsManagerStoreType,
  UseUndoRedoOptions,
} from "../types/zustand/flowsManager";
import {
  extractFieldsFromComponenents,
  processFlows,
} from "../utils/reactflowUtils";
import useAlertStore from "./alertStore";
import useFlowStore from "./flowStore";
import { useFolderStore } from "./foldersStore";
import { useTypesStore } from "./typesStore";

const defaultOptions: UseUndoRedoOptions = {
  maxHistorySize: 100,
  enableShortcuts: true,
};

const past = {};
const future = {};

const useFlowsManagerStore = create<FlowsManagerStoreType>((set, get) => ({
  examples: [],
  setExamples: (examples: FlowType[]) => {
    set({ examples });
  },
  currentFlowId: "",
  setCurrentFlow: (flow: FlowType) => {
    set((state) => ({
      currentFlow: flow,
      currentFlowId: flow.id,
    }));
  },
  getFlowById: (id: string) => {
    return get().flows.find((flow) => flow.id === id);
  },
  setCurrentFlowId: (currentFlowId: string) => {
    set((state) => ({
      currentFlowId,
      currentFlow: state.flows.find((flow) => flow.id === currentFlowId),
    }));
  },
  flows: [],
  allFlows: [],
  setAllFlows: (allFlows: FlowType[]) => {
    set({ allFlows });
  },
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
  refreshFlows: () => {
    return new Promise<void>((resolve, reject) => {
      set({ isLoading: true });

      const starterFolderId = useFolderStore.getState().starterProjectId;

      readFlowsFromDatabase()
        .then((dbData) => {
          if (dbData) {
            const { data, flows } = processFlows(dbData);
            const examples = flows.filter(
              (flow) => flow.folder_id === starterFolderId,
            );
            get().setExamples(examples);

            const flowsWithoutStarterFolder = flows.filter(
              (flow) => flow.folder_id !== starterFolderId,
            );

            get().setFlows(flowsWithoutStarterFolder);
            useTypesStore.setState((state) => ({
              data: { ...state.data, ["saved_components"]: data },
              ComponentFields: extractFieldsFromComponenents({
                ...state.data,
                ["saved_components"]: data,
              }),
            }));
            set({ isLoading: false });
            resolve();
          }
        })
        .catch((e) => {
          set({ isLoading: false });
          useAlertStore.getState().setErrorData({
            title: "Could not load flows from database",
          });
          reject(e);
        });
    });
  },
  autoSaveCurrentFlow: (nodes: Node[], edges: Edge[], viewport: Viewport) => {
    if (get().currentFlow) {
      get().saveFlow(
        { ...get().currentFlow!, data: { nodes, edges, viewport } },
        true,
      );
    }
  },
  saveFlow: (flow: FlowType, silent?: boolean) => {
    set({ saveLoading: true }); // set saveLoading true immediately
    return get().saveFlowDebounce(flow, silent); // call the debounced function directly
  },
  saveFlowDebounce: pDebounce((flow: FlowType, silent?: boolean) => {
    const folderUrl = useFolderStore.getState().folderUrl;
    const hasFolderUrl = folderUrl != null && folderUrl !== "";

    flow.folder_id = hasFolderUrl
      ? useFolderStore.getState().folderUrl
      : useFolderStore.getState().myCollectionId ?? "";

    set({ saveLoading: true });
    return new Promise<void>((resolve, reject) => {
      updateFlowInDatabase(flow)
        .then((updatedFlow) => {
          if (updatedFlow) {
            // updates flow in state
            if (!silent) {
              useAlertStore
                .getState()
                .setSuccessData({ title: "Changes saved successfully" });
            }
            get().setFlows(
              get().flows.map((flow) => {
                if (flow.id === updatedFlow.id) {
                  return updatedFlow;
                }
                return flow;
              }),
            );
            //update tabs state

            resolve();
            set({ saveLoading: false });
          }
        })
        .catch((err) => {
          useAlertStore.getState().setErrorData({
            title: "Error while saving changes",
            list: [(err as AxiosError).message],
          });
          reject(err);
        });
    });
  }, SAVE_DEBOUNCE_TIME),
  removeFlow: async (id: string | string[]) => {
    return new Promise<void>((resolve, reject) => {
      if (Array.isArray(id)) {
        multipleDeleteFlowsComponents(id)
          .then(() => {
            const { data, flows } = processFlows(
              get().flows.filter((flow) => !id.includes(flow.id)),
            );
            get().setFlows(flows);
            set({ isLoading: false });
            useTypesStore.setState((state) => ({
              data: { ...state.data, ["saved_components"]: data },
              ComponentFields: extractFieldsFromComponenents({
                ...state.data,
                ["saved_components"]: data,
              }),
            }));
            resolve();
          })
          .catch((e) => reject(e));
      } else {
        const index = get().flows.findIndex((flow) => flow.id === id);
        if (index >= 0) {
          deleteFlowFromDatabase(id)
            .then(() => {
              const { data, flows } = processFlows(
                get().flows.filter((flow) => flow.id !== id),
              );
              get().setFlows(flows);
              set({ isLoading: false });
              useTypesStore.setState((state) => ({
                data: { ...state.data, ["saved_components"]: data },
                ComponentFields: extractFieldsFromComponenents({
                  ...state.data,
                  ["saved_components"]: data,
                }),
              }));
              resolve();
            })
            .catch((e) => reject(e));
        }
      }
    });
  },
  deleteComponent: async (key: string) => {
    return new Promise<void>((resolve) => {
      let componentFlow = get().flows.find(
        (componentFlow) =>
          componentFlow.is_component && componentFlow.name === key,
      );

      if (componentFlow) {
        get()
          .removeFlow(componentFlow.id)
          .then(() => {
            resolve();
          });
      }
    });
  },
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
}));

export default useFlowsManagerStore;
