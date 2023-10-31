import { AxiosError } from "axios";
import {
  ReactNode,
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { Edge, Node, ReactFlowJsonObject } from "reactflow";
import ShortUniqueId from "short-unique-id";
import { skipNodeUpdate } from "../constants/constants";
import {
  deleteFlowFromDatabase,
  downloadFlowsFromDatabase,
  readFlowsFromDatabase,
  saveFlowToDatabase,
  updateFlowInDatabase,
  uploadFlowsToDatabase,
} from "../controllers/API";
import { APIClassType, APITemplateType } from "../types/api";
import {
  FlowType,
  NodeType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import { FlowsContextType, FlowsState } from "../types/tabs";
import {
  addVersionToDuplicates,
  checkOldEdgesHandles,
  scapeJSONParse,
  scapedJSONStringfy,
  updateEdgesHandleIds,
  updateIds,
  updateTemplate,
} from "../utils/reactflowUtils";
import { getRandomDescription, getRandomName } from "../utils/utils";
import { alertContext } from "./alertContext";
import { AuthContext } from "./authContext";
import { flowManagerContext } from "./flowManagerContext";
import { typesContext } from "./typesContext";

const uid = new ShortUniqueId({ length: 5 });

const FlowsContextInitialValue: FlowsContextType = {
  selectedFlowId: "",
  setFlowId: (index: string) => {},
  isLoading: true,
  flows: [],
  removeFlow: (id: string) => {},
  addFlow: async (newProject: boolean, flowData?: FlowType) => "",
  updateFlow: (newFlow: FlowType) => {},
  downloadFlows: () => {},
  uploadFlows: () => {},
  uploadFlow: async () => "",
  hardReset: () => {},
  saveFlow: async (flow: FlowType, silent?: boolean) => {},
  lastCopiedSelection: null,
  setLastCopiedSelection: (selection: any) => {},
  tabsState: {},
  setTabsState: (state: FlowsState) => {},
  getNodeId: (nodeType: string) => "",
};

export const FlowsContext = createContext<FlowsContextType>(
  FlowsContextInitialValue
);

export function FlowsProvider({ children }: { children: ReactNode }) {
  const { setErrorData, setNoticeData, setSuccessData } =
    useContext(alertContext);
  const { getAuthentication, isAuthenticated } = useContext(AuthContext);

  const [selectedFlowId, setFlowId] = useState("");

  const [isLoading, setIsLoading] = useState(true);

  const [flows, setFlows] = useState<Array<FlowType>>([]);
  const [id, setId] = useState(uid());
  const { templates } = useContext(typesContext);
  const { reactFlowInstance } = useContext(flowManagerContext);
  const [lastCopiedSelection, setLastCopiedSelection] = useState<{
    nodes: any;
    edges: any;
  } | null>(null);
  const [tabsState, setTabsState] = useState<FlowsState>({});

  useEffect(() => {
    if (!isAuthenticated) {
      hardReset();
    }
  }, [isAuthenticated]);

  const newNodeId = useRef(uid());
  function incrementNodeId() {
    newNodeId.current = uid();
    return newNodeId.current;
  }

  function refreshFlows() {
    setIsLoading(true);
    getTabsDataFromDB().then((DbData) => {
      if (DbData && Object.keys(templates).length > 0) {
        try {
          processDBData(DbData);
          updateStateWithDbData(DbData);
          setIsLoading(false);
        } catch (e) {}
      }
    });
  }

  useEffect(() => {
    // If the user is authenticated, fetch the types. This code is important to check if the user is auth because of the execution order of the useEffect hooks.
    if (getAuthentication() === true) {
      // get data from db
      //get tabs locally saved
      // let tabsData = getLocalStorageTabsData();
      refreshFlows();
    }
  }, [templates, getAuthentication()]);

  function getTabsDataFromDB() {
    //get tabs from db
    return readFlowsFromDatabase();
  }

  function processDBData(DbData: FlowType[]) {
    DbData.forEach((flow: FlowType) => {
      try {
        if (!flow.data) {
          return;
        }
        processDataFromFlow(flow, false);
      } catch (e) {}
    });
  }

  function processFlowEdges(flow: FlowType) {
    if (!flow.data || !flow.data.edges) return;
    if (checkOldEdgesHandles(flow.data.edges)) {
      const newEdges = updateEdgesHandleIds(flow.data);
      flow.data.edges = newEdges;
    }
    //update edges colors
    flow.data.edges.forEach((edge) => {
      edge.className = "";
      edge.style = { stroke: "#555" };
    });
  }

  function updateDisplay_name(node: NodeType, template: APIClassType) {
    node.data.node!.display_name = template["display_name"] || node.data.type;
  }

  function updateNodeDocumentation(node: NodeType, template: APIClassType) {
    node.data.node!.documentation = template["documentation"];
  }

  function processFlowNodes(flow: FlowType) {
    if (!flow.data || !flow.data.nodes) return;
    flow.data.nodes.forEach((node: NodeType) => {
      if (node.data.node?.flow) return;
      if (skipNodeUpdate.includes(node.data.type)) return;
      const template = templates[node.data.type];
      if (!template) {
        setErrorData({ title: `Unknown node type: ${node.data.type}` });
        return;
      }
      if (Object.keys(template["template"]).length > 0) {
        updateDisplay_name(node, template);
        updateNodeBaseClasses(node, template);
        //update baseclasses in edges
        updateNodeEdges(flow, node, template);
        updateNodeDescription(node, template);
        updateNodeTemplate(node, template);
        updateNodeDocumentation(node, template);
      }
    });
  }

  function updateNodeBaseClasses(node: NodeType, template: APIClassType) {
    node.data.node!.base_classes = template["base_classes"];
  }

  function updateNodeEdges(
    flow: FlowType,
    node: NodeType,
    template: APIClassType
  ) {
    flow.data!.edges.forEach((edge) => {
      if (edge.source === node.id) {
        let sourceHandleObject: sourceHandleType = scapeJSONParse(
          edge.sourceHandle!
        );
        sourceHandleObject.baseClasses = template["base_classes"];
        edge.data.sourceHandle = sourceHandleObject;
        edge.sourceHandle = scapedJSONStringfy(sourceHandleObject);
      }
    });
  }

  function updateNodeDescription(node: NodeType, template: APIClassType) {
    node.data.node!.description = template["description"];
  }

  function updateNodeTemplate(node: NodeType, template: APIClassType) {
    node.data.node!.template = updateTemplate(
      template["template"] as unknown as APITemplateType,
      node.data.node!.template as APITemplateType
    );
  }

  function updateStateWithDbData(tabsData: FlowType[]) {
    setFlows(tabsData);
  }

  function hardReset() {
    newNodeId.current = uid();
    setFlowId("");
    setFlows([]);
    setIsLoading(true);
    setId(uid());
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

  function getNodeId(nodeType: string) {
    return nodeType + "-" + incrementNodeId();
  }

  /**
   * Creates a file input and listens to a change event to upload a JSON flow file.
   * If the file type is application/json, the file is read and parsed into a JSON object.
   * The resulting JSON object is passed to the addFlow function.
   */
  async function uploadFlow(
    newProject: boolean,
    file?: File
  ): Promise<String | undefined> {
    let id;
    if (file) {
      let text = await file.text();
      let fileData = JSON.parse(text);
      if (fileData.flows) {
        fileData.flows.forEach((flow: FlowType) => {
          id = addFlow(newProject, flow);
        });
      }
      // parse the text into a JSON object
      let flow: FlowType = JSON.parse(text);

      id = await addFlow(newProject, flow);
    } else {
      // create a file input
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".json";
      // add a change event listener to the file input
      id = await new Promise((resolve) => {
        input.onchange = async (e: Event) => {
          if (
            (e.target as HTMLInputElement).files![0].type === "application/json"
          ) {
            const currentfile = (e.target as HTMLInputElement).files![0];
            let text = await currentfile.text();
            let flow: FlowType = JSON.parse(text);
            const flowId = await addFlow(newProject, flow);
            resolve(flowId);
          }
        };
        // trigger the file input click event to open the file dialog
        input.click();
      });
    }
    return id;
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
  function removeFlow(id: string) {
    const index = flows.findIndex((flow) => flow.id === id);
    if (index >= 0) {
      deleteFlowFromDatabase(id).then(() => {
        setFlows(flows.filter((flow) => flow.id !== id));
      });
    }
  }
  const addFlow = async (
    newProject: Boolean,
    flow?: FlowType
  ): Promise<String | undefined> => {
    if (newProject) {
      let flowData = flow
        ? processDataFromFlow(flow)
        : { nodes: [], edges: [], viewport: { zoom: 1, x: 0, y: 0 } };

      // Create a new flow with a default name if no flow is provided.
      const newFlow = createNewFlow(flowData, flow!);

      const flowName = addVersionToDuplicates(newFlow, flows);

      newFlow.name = flowName;

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
        { x: 10, y: 10 }
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
      if (refreshIds) updateIds(data, getNodeId); // Assuming updateIds is defined elsewhere
    }

    return data;
  };

  const updateEdges = (edges: Edge[]) => {
    edges.forEach((edge) => {
      const targetHandleObject: targetHandleType = scapeJSONParse(
        edge.targetHandle!
      );
      edge.className =
        (targetHandleObject.type === "Text"
          ? "stroke-gray-800 "
          : "stroke-gray-900 ") + " stroke-connection";
      edge.animated = targetHandleObject.type === "Text";
    });
  };

  const updateNodes = (nodes: Node[], edges: Edge[]) => {
    nodes.forEach((node) => {
      if (node.data.node?.flow) return;
      if (skipNodeUpdate.includes(node.data.type)) return;
      const template = templates[node.data.type];
      if (!template) {
        setErrorData({ title: `Unknown node type: ${node.data.type}` });
        return;
      }
      if (Object.keys(template["template"]).length > 0) {
        node.data.node.base_classes = template["base_classes"];
        edges.forEach((edge) => {
          let sourceHandleObject: sourceHandleType = scapeJSONParse(
            edge.sourceHandle!
          );
          if (edge.source === node.id) {
            let newSourceHandle = sourceHandleObject;
            newSourceHandle.baseClasses.concat(template["base_classes"]);
            edge.sourceHandle = scapedJSONStringfy(newSourceHandle);
          }
        });
        node.data.node.description = template["description"];
        node.data.node.template = updateTemplate(
          template["template"] as unknown as APITemplateType,
          node.data.node.template as APITemplateType
        );
      }
    });
  };

  const createNewFlow = (
    flowData: ReactFlowJsonObject | null,
    flow: FlowType
  ) => ({
    description: flow?.description ?? getRandomDescription(),
    name: flow?.name ?? getRandomName(),
    data: flowData,
    id: "",
  });

  const addFlowToLocalState = (newFlow: FlowType) => {
    setFlows((prevState) => {
      return [...prevState, newFlow];
    });
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
      return newFlows;
    });
  }

  async function saveFlow(newFlow: FlowType, silent?: boolean) {
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
        setTabsState((prev) => {
          return {
            ...prev,
            [selectedFlowId]: {
              ...prev[selectedFlowId],
              isPending: false,
            },
          };
        });
      }
    } catch (err) {
      setErrorData({
        title: "Error while saving changes",
        list: [(err as AxiosError).message],
      });
    }
  }

  return (
    <FlowsContext.Provider
      value={{
        saveFlow,
        lastCopiedSelection,
        setLastCopiedSelection,
        hardReset,
        selectedFlowId,
        setFlowId,
        flows,
        removeFlow,
        addFlow,
        updateFlow,
        downloadFlows,
        uploadFlows,
        uploadFlow,
        getNodeId,
        tabsState,
        setTabsState,
        isLoading,
      }}
    >
      {children}
    </FlowsContext.Provider>
  );
}
