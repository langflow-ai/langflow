import { AxiosError } from "axios";
import { Edge, Node, Viewport } from "reactflow";
import { create } from "zustand";
import {
  readFlowsFromDatabase,
  updateFlowInDatabase,
  uploadFlowsToDatabase,
} from "../controllers/API";
import { FlowType } from "../types/flow";
import { FlowState } from "../types/tabs";
import { FlowsManagerStoreType } from "../types/zustand/flowsManager";
import { processFlows } from "../utils/reactflowUtils";
import useAlertStore from "./alertStore";
import useFlowStore from "./flowStore";
import { useTypesStore } from "./typesStore";

let saveTimeoutId: NodeJS.Timeout | null = null;

const useFlowsManagerStore = create<FlowsManagerStoreType>((set, get) => ({
  currentFlowId: "",
  setCurrentFlowId: (currentFlowId: string) => {
    set((state) => ({
      currentFlowId,
      currentFlowState: state.flowsState[state.currentFlowId],
      currentFlow: state.flows.find((flow) => flow.id === currentFlowId),
    }));
  },
  flows: [],
  setFlows: (flows: FlowType[]) => {
    set({
      flows,
      currentFlow: flows.find((flow) => flow.id === get().currentFlowId),
    });
  },
  currentFlow: undefined,
  isLoading: true,
  setIsLoading: (isLoading: boolean) => set({ isLoading }),
  flowsState: {},
  currentFlowState: undefined,
  setCurrentFlowState: (
    flowState: FlowState | ((oldState: FlowState | undefined) => FlowState)
  ) => {
    const newFlowState =
      typeof flowState === "function"
        ? flowState(get().currentFlowState)
        : flowState;
    set((state) => ({
      flowsState: {
        ...state.flowsState,
        [state.currentFlowId]: newFlowState,
      },
      currentFlowState: newFlowState,
    }));
  },
  refreshFlows: () => {
    return new Promise<void>((resolve, reject) => {
      set({ isLoading: true });
      readFlowsFromDatabase()
        .then((dbData) => {
          if (dbData) {
            const { data, flows } = processFlows(dbData, false);
            get().setFlows(flows);
            set({ isLoading: false });
            useTypesStore.setState((state) => ({
              data: { ...state.data, ["saved_components"]: data },
            }));
            resolve();
          }
        })
        .catch((e) => {
          useAlertStore.getState().setErrorData({
            title: "Could not load flows from database",
          });
          reject(e);
        });
    });
  },
  autoSaveCurrentFlow: (nodes: Node[], edges: Edge[], viewport: Viewport) => {
    // Clear the previous timeout if it exists.
    if (saveTimeoutId) {
      clearTimeout(saveTimeoutId);
    }

    // Set up a new timeout.
    saveTimeoutId = setTimeout(() => {
      if (get().currentFlow) {
        get().saveFlow(
          { ...get().currentFlow!, data: { nodes, edges, viewport } },
          true
        );
      }
    }, 300); // Delay of 300ms.
  },
  saveFlow: (flow: FlowType, silent?: boolean) => {
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
              })
            );
            //update tabs state

            useFlowStore.setState({ isPending: false });
            resolve();
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
  },
  uploadFlows: () => {
    return new Promise<void>((resolve) => {
      const input = document.createElement("input");
      input.type = "file";
      // add a change event listener to the file input
      input.onchange = (event: Event) => {
        // check if the file type is application/json
        if (
          (event.target as HTMLInputElement).files![0].type ===
          "application/json"
        ) {
          // get the file from the file input
          const file = (event.target as HTMLInputElement).files![0];
          // read the file as text
          const formData = new FormData();
          formData.append("file", file);
          uploadFlowsToDatabase(formData).then(() => {
            get()
              .refreshFlows()
              .then(() => {
                resolve();
              });
          });
        }
      };
      // trigger the file input click event to open the file dialog
      input.click();
    });
  },
}));

export default useFlowsManagerStore;
