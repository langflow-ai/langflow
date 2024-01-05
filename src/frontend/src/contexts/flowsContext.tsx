import { AxiosError } from "axios";
import _, { cloneDeep } from "lodash";
import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
} from "react";
import {
  Edge,
  EdgeChange,
  Node,
  NodeChange,
  ReactFlowJsonObject,
  Viewport,
  XYPosition,
  addEdge,
  useEdgesState,
  useNodesState,
} from "reactflow";
import ShortUniqueId from "short-unique-id";
import {
  deleteFlowFromDatabase,
  downloadFlowsFromDatabase,
  getVersion,
  readFlowsFromDatabase,
  saveFlowToDatabase,
  updateFlowInDatabase,
  uploadFlowsToDatabase,
} from "../controllers/API";
import { APIClassType } from "../types/api";
import { tweakType } from "../types/components";
import {
  FlowType,
  NodeDataType,
  NodeType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import { FlowsContextType, FlowsState } from "../types/tabs";
import {
  addVersionToDuplicates,
  checkOldEdgesHandles,
  cleanEdges,
  createFlowComponent,
  processFlowEdges,
  removeFileNameFromComponents,
  scapeJSONParse,
  scapedJSONStringfy,
  updateEdges,
  updateEdgesHandleIds,
  updateIds,
} from "../utils/reactflowUtils";
import {
  createRandomKey,
  getRandomDescription,
  getRandomName,
} from "../utils/utils";
import { alertContext } from "./alertContext";
import { AuthContext } from "./authContext";
import { typesContext } from "./typesContext";
import useFlowStore from "../stores/flowStore";

const uid = new ShortUniqueId({ length: 5 });

const FlowsContextInitialValue: FlowsContextType = {
  //Remove tab id and get current id from url
  tabId: "",
  setTabId: (index: string) => {},
  isLoading: true,
  flows: [],
  setVersion: () => {},
  removeFlow: (id: string) => {},
  addFlow: async (
    newProject: boolean,
    flowData?: FlowType,
    override?: boolean
  ) => "",
  downloadFlow: (flow: FlowType) => {},
  downloadFlows: () => {},
  uploadFlows: () => {},
  uploadFlow: async () => "",
  saveFlow: async (flow?: FlowType, silent?: boolean) => {},
  tabsState: {},
  setTabsState: () => {},
  saveComponent: async (component: NodeDataType, override: boolean) => "",
  deleteComponent: (key: string) => {},
  version: "",
  refreshFlows: () => {},
};

export const FlowsContext = createContext<FlowsContextType>(
  FlowsContextInitialValue
);

export function FlowsProvider({ children }: { children: ReactNode }) {
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { getAuthentication, isAuthenticated } = useContext(AuthContext);

  const [tabId, setTabId] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [flows, setFlows] = useState<Array<FlowType>>([]);
  const [tabsState, setTabsState] = useState<FlowsState>({});
  const {setData} = useContext(typesContext);

  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const reactFlowInstance = useFlowStore((state) => state.reactFlowInstance);
  const setPending = useFlowStore((state) => state.setPending);
  const paste = useFlowStore((state) => state.paste);

  function refreshFlows() {
    setIsLoading(true);
    getTabsDataFromDB().then((DbData) => {
      if (DbData) {
        try {
          processFlows(DbData, false);
          setFlows(DbData);
          setIsLoading(false);
        } catch (e) {}
      }
    });
  }

  function getTabsDataFromDB() {
    //get tabs from db
    return readFlowsFromDatabase();
  }

  function processFlows(DbData: FlowType[], skipUpdate = true) {
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
            createRandomKey(
              (flow.data.nodes[0].data as NodeDataType).type,
              uid()
            )
          ] = _.cloneDeep((flow.data.nodes[0].data as NodeDataType).node!);
          return;
        }
        if (!skipUpdate) processDataFromFlow(flow, false);
      } catch (e) {
        console.log(e);
      }
    });
    setData((prev) => {
      let newData = cloneDeep(prev);
      newData["saved_components"] = cloneDeep(savedComponents);
      return newData;
    });
  }

  /**
   * Downloads the current flow as a JSON file
   */
  function downloadFlow(
    flow: FlowType,
    flowName: string,
    flowDescription?: string
  ) {
    let clonedFlow = cloneDeep(flow);
    removeFileNameFromComponents(clonedFlow);
    // create a data URI with the current flow data
    const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
      JSON.stringify({
        ...clonedFlow,
        name: flowName,
        description: flowDescription,
      })
    )}`;

    // create a link element and set its properties
    const link = document.createElement("a");
    link.href = jsonString;
    link.download = `${
      flowName && flowName != ""
        ? flowName
        : flows.find((f) => f.id === tabId)!.name
    }.json`;

    // simulate a click on the link element to trigger the download
    link.click();
  }

  function downloadFlows() {
    downloadFlowsFromDatabase().then((flows) => {
      const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
        JSON.stringify(flows)
      )}`;

      // create a link element and set its properties
      const link = document.createElement("a");
      link.href = jsonString;
      link.download = `flows.json`;

      // simulate a click on the link element to trigger the download
      link.click();
    });
  }
  /**
   * Creates a file input and listens to a change event to upload a JSON flow file.
   * If the file type is application/json, the file is read and parsed into a JSON object.
   * The resulting JSON object is passed to the addFlow function.
   */
  async function uploadFlow({
    newProject,
    file,
    isComponent = false,
    position = { x: 10, y: 10 },
  }: {
    newProject: boolean;
    file?: File;
    isComponent?: boolean;
    position?: XYPosition;
  }): Promise<String | never> {
    return new Promise(async (resolve, reject) => {
      let id;
      if (file) {
        let text = await file.text();
        let fileData = JSON.parse(text);
        if (
          newProject &&
          ((!fileData.is_component && isComponent === true) ||
            (fileData.is_component !== undefined &&
              fileData.is_component !== isComponent))
        ) {
          reject("You cannot upload a component as a flow or vice versa");
        } else {
          if (fileData.flows) {
            fileData.flows.forEach((flow: FlowType) => {
              id = addFlow(newProject, flow, undefined, position);
            });
            resolve("");
          } else {
            id = await addFlow(newProject, fileData, undefined, position);
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
              id = await addFlow(newProject, fileData);
              resolve(id);
            }
          }
        };
        // trigger the file input click event to open the file dialog
        input.click();
      }
    });
  }

  function uploadFlows() {
    // create a file input
    const input = document.createElement("input");
    input.type = "file";
    // add a change event listener to the file input
    input.onchange = (event: Event) => {
      // check if the file type is application/json
      if (
        (event.target as HTMLInputElement).files![0].type === "application/json"
      ) {
        // get the file from the file input
        const file = (event.target as HTMLInputElement).files![0];
        // read the file as text
        const formData = new FormData();
        formData.append("file", file);
        uploadFlowsToDatabase(formData).then(() => {
          refreshFlows();
        });
      }
    };
    // trigger the file input click event to open the file dialog
    input.click();
  }
  /**
   * Removes a flow from an array of flows based on its id.
   * Updates the state of flows and tabIndex using setFlows and setTabIndex hooks.
   * @param {string} id - The id of the flow to remove.
   */
  async function removeFlow(id: string) {
    const index = flows.findIndex((flow) => flow.id === id);
    if (index >= 0) {
      await deleteFlowFromDatabase(id);
      //removes component from data if there is any
      setFlows(flows.filter((flow) => flow.id !== id));
      processFlows(flows.filter((flow) => flow.id !== id));
    }
  }

  const addFlow = async (
    newProject: Boolean,
    flow?: FlowType,
    override?: boolean,
    position?: XYPosition
  ): Promise<String | undefined> => {
    if (newProject) {
      let flowData = flow
        ? processDataFromFlow(flow)
        : { nodes: [], edges: [], viewport: { zoom: 1, x: 0, y: 0 } };

      // Create a new flow with a default name if no flow is provided.

      if (override) {
        deleteComponent(flow!.name);
        const newFlow = createNewFlow(flowData, flow!);
        const { id } = await saveFlowToDatabase(newFlow);
        newFlow.id = id;
        //setTimeout  to prevent update state with wrong state
        setTimeout(() => {
          addFlowToLocalState(newFlow);
        }, 200);
        // addFlowToLocalState(newFlow);
        return;
      }

      const newFlow = createNewFlow(flowData, flow!);

      const newName = addVersionToDuplicates(newFlow, flows);

      newFlow.name = newName;
      try {
        const { id } = await saveFlowToDatabase(newFlow);
        // Change the id to the new id.
        newFlow.id = id;

        // Add the new flow to the list of flows.
        addFlowToLocalState(newFlow);

        // Return the id
        return id;
      } catch (error) {
        // Handle the error if needed
        throw error; // Re-throw the error so the caller can handle it if needed
      }
    } else {
      paste(
        { nodes: flow!.data!.nodes, edges: flow!.data!.edges },
        position ?? { x: 10, y: 10 }
      );
    }
  };

  const processDataFromFlow = (flow: FlowType, refreshIds = true) => {
    let data = flow?.data ? flow.data : null;
    if (data) {
      processFlowEdges(flow);
      //prevent node update for now
      // processFlowNodes(flow);
      //add animation to text type edges
      updateEdges(data.edges);
      // updateNodes(data.nodes, data.edges);
      if (refreshIds) updateIds(data); // Assuming updateIds is defined elsewhere
    }
    return data;
  };

  const createNewFlow = (
    flowData: ReactFlowJsonObject | null,
    flow: FlowType
  ) => ({
    description: flow?.description ?? getRandomDescription(),
    name: flow?.name ?? getRandomName(),
    data: flowData,
    id: "",
    is_component: flow?.is_component ?? false,
  });

  const addFlowToLocalState = (newFlow: FlowType) => {
    let newFlows: FlowType[] = [];
    setFlows((prevState) => {
      newFlows = newFlows.concat(prevState);
      newFlows.push(newFlow);
      return [...prevState, newFlow];
    });
    processFlows(newFlows);
  };

  /**
   * Updates an existing flow with new data
   * @param newFlow - The new flow object containing the updated data
   */
  function updateFlow(newFlow: FlowType) {
    setFlows((prevState) => {
      const newFlows = [...prevState];
      const index = newFlows.findIndex((flow) => flow.id === newFlow.id);
      if (index !== -1) {
        newFlows[index].description = newFlow.description ?? "";
        newFlows[index].data = newFlow.data;
        newFlows[index].name = newFlow.name;
      }
      newFlow = {
        ...newFlow,
      };
      return newFlows;
    });
  }

  const saveTimeoutId = useRef<NodeJS.Timeout | null>(null);

  const saveCurrentFlow = (
    nodes: Node[],
    edges: Edge[],
    viewport: Viewport
  ) => {
    // Clear the previous timeout if it exists.
    if (saveTimeoutId.current) {
      clearTimeout(saveTimeoutId.current);
    }

    // Set up a new timeout.
    saveTimeoutId.current = setTimeout(() => {
      const currentFlow = flows.find((flow: FlowType) => flow.id === tabId);
      if (currentFlow) {
        saveFlow({ ...currentFlow, data: { nodes, edges, viewport } }, true);
      }
    }, 300); // Delay of 300ms.
  };

  async function saveFlow(flow?: FlowType, silent?: boolean) {
    let newFlow;
    if (!flow) {
      const currentFlow = flows.find((flow) => flow.id === tabId)!;
      newFlow = {
        ...currentFlow,
        data: {
          nodes,
          edges,
          viewport: reactFlowInstance?.getViewport() ?? { zoom: 1, x: 0, y: 0 },
        },
      };
    } else {
      newFlow = flow;
    }

    try {
      // updates flow in db
      const updatedFlow = await updateFlowInDatabase(newFlow);
      if (updatedFlow) {
        // updates flow in state
        if (!silent) {
          setSuccessData({ title: "Changes saved successfully" });
        }
        updateFlow(newFlow);
        //update tabs state
        setPending(false);
      }
    } catch (err) {
      setErrorData({
        title: "Error while saving changes",
        list: [(err as AxiosError).message],
      });
    }
  }

  function saveComponent(component: NodeDataType, override: boolean) {
    component.node!.official = false;
    return addFlow(true, createFlowComponent(component, version), override);
  }

  function deleteComponent(key: string) {
    let componentFlow = flows.find(
      (componentFlow) =>
        componentFlow.is_component && componentFlow.name === key
    );

    if (componentFlow) {
      removeFlow(componentFlow.id);
    }
  }

  // Initialize state variable for the version
  const [version, setVersion] = useState("");


  return (
    <FlowsContext.Provider
      value={{
        version,
        setVersion,
        flows,
        saveFlow,
        tabId,
        setTabId,
        removeFlow,
        addFlow,
        downloadFlow,
        downloadFlows,
        uploadFlows,
        uploadFlow,
        tabsState,
        setTabsState,
        refreshFlows,
        isLoading,
        saveComponent,
        deleteComponent,
      }}
    >
      {children}
    </FlowsContext.Provider>
  );
}
