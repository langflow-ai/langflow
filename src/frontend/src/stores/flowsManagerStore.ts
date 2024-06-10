import { cloneDeep } from "lodash";
import pDebounce from "p-debounce";
import { Edge, Node, Viewport, XYPosition } from "reactflow";
import { create } from "zustand";
import { SAVE_DEBOUNCE_TIME } from "../constants/constants";
import {
  deleteFlowFromDatabase,
  multipleDeleteFlowsComponents,
  readFlowsFromDatabase,
  saveFlowToDatabase,
  updateFlowInDatabase,
  uploadFlowsToDatabase,
} from "../controllers/API";
import { FlowType, NodeDataType } from "../types/flow";
import {
  FlowsManagerStoreType,
  UseUndoRedoOptions,
} from "../types/zustand/flowsManager";
import {
  addVersionToDuplicates,
  createFlowComponent,
  createNewFlow,
  extractFieldsFromComponenents,
  processDataFromFlow,
  processFlows,
} from "../utils/reactflowUtils";
import useAlertStore from "./alertStore";
import { useDarkStore } from "./darkStore";
import useFlowStore from "./flowStore";
import { useFolderStore } from "./foldersStore";
import { useTypesStore } from "./typesStore";

let saveTimeoutId: NodeJS.Timeout | null = null;

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
  isLoading: true,
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
          reject(err);
          set({ saveLoading: false });
          throw err;
        });
    });
  }, SAVE_DEBOUNCE_TIME),
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
  addFlow: async (
    newProject: Boolean,
    flow?: FlowType,
    override?: boolean,
    position?: XYPosition,
    fromDragAndDrop?: boolean,
  ): Promise<string | undefined> => {
    if (newProject) {
      let flowData = flow
        ? processDataFromFlow(flow)
        : { nodes: [], edges: [], viewport: { zoom: 1, x: 0, y: 0 } };

      // Create a new flow with a default name if no flow is provided.
      const folder_id = useFolderStore.getState().folderUrl;
      const my_collection_id = useFolderStore.getState().myCollectionId;

      if (override) {
        get().deleteComponent(flow!.name);
        const newFlow = createNewFlow(
          flowData!,
          flow!,
          folder_id || my_collection_id!,
        );
        const { id } = await saveFlowToDatabase(newFlow);
        newFlow.id = id;
        //setTimeout  to prevent update state with wrong state
        setTimeout(() => {
          const { data, flows } = processFlows([newFlow, ...get().flows]);
          get().setFlows(flows);
          set({ isLoading: false });
          useTypesStore.setState((state) => ({
            data: { ...state.data, ["saved_components"]: data },
            ComponentFields: extractFieldsFromComponenents({
              ...state.data,
              ["saved_components"]: data,
            }),
          }));
        }, 200);
        // addFlowToLocalState(newFlow);
        return;
      }
      const newFlow = createNewFlow(
        flowData!,
        flow!,
        folder_id || my_collection_id!,
      );

      const newName = addVersionToDuplicates(newFlow, get().flows);

      newFlow.name = newName;
      newFlow.folder_id = useFolderStore.getState().folderUrl;

      try {
        const { id } = await saveFlowToDatabase(newFlow);
        // Change the id to the new id.
        newFlow.id = id;

        // Add the new flow to the list of flows.
        const { data, flows } = processFlows([newFlow, ...get().flows]);
        get().setFlows(flows);
        set({ isLoading: false });
        useTypesStore.setState((state) => ({
          data: { ...state.data, ["saved_components"]: data },
          ComponentFields: extractFieldsFromComponenents({
            ...state.data,
            ["saved_components"]: data,
          }),
        }));

        // Return the id
        return id;
      } catch (error) {
        // Handle the error if needed
        throw error; // Re-throw the error so the caller can handle it if needed
      }
    } else {
      useFlowStore
        .getState()
        .paste(
          { nodes: flow!.data!.nodes, edges: flow!.data!.edges },
          position ?? { x: 10, y: 10 },
        );
    }
  },
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
  uploadFlow: async ({
    newProject,
    file,
    isComponent,
    position = { x: 10, y: 10 },
  }: {
    newProject: boolean;
    file?: File;
    isComponent: boolean | null;
    position?: XYPosition;
  }): Promise<string | never> => {
    return new Promise(async (resolve, reject) => {
      let id;
      if (file) {
        let text = await file.text();
        let fileData = JSON.parse(text);
        if (
          newProject &&
          isComponent !== null &&
          ((!fileData.is_component && isComponent === true) ||
            (fileData.is_component !== undefined &&
              fileData.is_component !== isComponent))
        ) {
          reject("You cannot upload a component as a flow or vice versa");
        } else {
          if (fileData.flows) {
            fileData.flows.forEach((flow: FlowType) => {
              id = get().addFlow(newProject, flow, undefined, position);
            });
            resolve("");
          } else {
            id = await get().addFlow(
              newProject,
              fileData,
              undefined,
              position,
              true,
            );
            resolve(id);
          }
        }
      } else {
        // create a file input
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".json";
        // add a change event listener to the file input
        input.onchange = async (e: Event) => {
          if (
            (e.target as HTMLInputElement).files![0].type === "application/json"
          ) {
            const currentfile = (e.target as HTMLInputElement).files![0];
            let text = await currentfile.text();
            let fileData: FlowType = await JSON.parse(text);

            if (
              (!fileData.is_component && isComponent === true) ||
              (fileData.is_component !== undefined &&
                fileData.is_component !== isComponent)
            ) {
              reject("You cannot upload a component as a flow or vice versa");
            } else {
              id = await get().addFlow(newProject, fileData);
              resolve(id);
            }
          }
        };
        // trigger the file input click event to open the file dialog
        input.click();
      }
    });
  },
  saveComponent: (component: NodeDataType, override: boolean) => {
    component.node!.official = false;
    return get().addFlow(
      true,
      createFlowComponent(component, useDarkStore.getState().version),
      override,
    );
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
