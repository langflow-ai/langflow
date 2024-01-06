import { cloneDeep } from "lodash";
import ShortUniqueId from "short-unique-id";
import { create } from "zustand";
import { readFlowsFromDatabase } from "../controllers/API";
import { APIClassType } from "../types/api";
import { FlowType, NodeDataType } from "../types/flow";
import { FlowState } from "../types/tabs";
import { FlowsManagerStoreType } from "../types/zustand/flowsManager";
import { processDataFromFlow } from "../utils/reactflowUtils";
import { createRandomKey } from "../utils/utils";
import { useTypesStore } from "./typesStore";
import useAlertStore from "./alertStore";

const uid = new ShortUniqueId({ length: 5 });

const processFlows = (DbData: FlowType[], skipUpdate = true) => {
  let savedComponents: { [key: string]: APIClassType } = {};
  DbData.forEach((flow: FlowType) => {
    try {
      if (!flow.data) {
        return;
      }
      if (flow.data && flow.is_component) {
        (flow.data.nodes[0].data as NodeDataType).node!.display_name =
          flow.name;
        savedComponents[
          createRandomKey((flow.data.nodes[0].data as NodeDataType).type, uid())
        ] = cloneDeep((flow.data.nodes[0].data as NodeDataType).node!);
        return;
      }
      if (!skipUpdate) processDataFromFlow(flow, false);
    } catch (e) {
      console.log(e);
    }
  });
  return { data: savedComponents, flows: DbData };
};

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
      readFlowsFromDatabase().then((dbData) => {
        if (dbData) {
          const { data, flows } = processFlows(dbData, false);
          set({ flows, isLoading: false });
          useTypesStore.setState((state) => ({
            data: { ...state.data, ["saved_components"]: data },
          }));
          resolve();
        }
      }).catch((e) => {
        useAlertStore.getState().setErrorData({
          title: "Could not load flows from database",
        });
        reject(e);
      });
    });
  },
}));

export default useFlowsManagerStore;
