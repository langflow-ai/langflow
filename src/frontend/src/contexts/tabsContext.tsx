import _ from "lodash";
import {
  ReactNode,
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { addEdge } from "reactflow";
import ShortUniqueId from "short-unique-id";
import {
  deleteFlowFromDatabase,
  downloadFlowsFromDatabase,
  readFlowsFromDatabase,
  saveFlowToDatabase,
  updateFlowInDatabase,
  uploadFlowsToDatabase,
} from "../controllers/API";
import { APIClassType, APITemplateType } from "../types/api";
import { FlowType, NodeType } from "../types/flow";
import { TabsContextType, TabsState } from "../types/tabs";
import {
  addVersionToDuplicates,
  updateIds,
  updateTemplate,
} from "../utils/reactflowUtils";
import { getRandomDescription, getRandomName } from "../utils/utils";
import { alertContext } from "./alertContext";
import { typesContext } from "./typesContext";

const uid = new ShortUniqueId({ length: 5 });

const TabsContextInitialValue: TabsContextType = {
  save: () => {},
  tabId: "",
  setTabId: (index: string) => {},
  flows: [],
  removeFlow: (id: string) => {},
  addFlow: async (flowData?: any) => "",
  updateFlow: (newFlow: FlowType) => {},
  incrementNodeId: () => uid(),
  downloadFlow: (flow: FlowType) => {},
  downloadFlows: () => {},
  uploadFlows: () => {},
  uploadFlow: () => {},
  isBuilt: false,
  setIsBuilt: (state: boolean) => {},
  hardReset: () => {},
  saveFlow: async (flow: FlowType) => {},
  lastCopiedSelection: null,
  setLastCopiedSelection: (selection: any) => {},
  tabsState: {},
  setTabsState: (state: TabsState) => {},
  getNodeId: (nodeType: string) => "",
  setTweak: (tweak: any) => {},
  getTweak: [],
  paste: (
    selection: { nodes: any; edges: any },
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) => {},
};

export const TabsContext = createContext<TabsContextType>(
  TabsContextInitialValue
);

export function TabsProvider({ children }: { children: ReactNode }) {
  const { setErrorData, setNoticeData } = useContext(alertContext);

  const [tabId, setTabId] = useState("");

  const [flows, setFlows] = useState<Array<FlowType>>([]);
  const [id, setId] = useState(uid());
  const { templates, reactFlowInstance } = useContext(typesContext);
  const [lastCopiedSelection, setLastCopiedSelection] = useState(null);
  const [tabsState, setTabsState] = useState<TabsState>({});
  const [getTweak, setTweak] = useState([]);

  const newNodeId = useRef(uid());
  function incrementNodeId() {
    newNodeId.current = uid();
    return newNodeId.current;
  }

  function save() {
    // added clone deep to avoid mutating the original object
    let Saveflows = _.cloneDeep(flows);
    if (Saveflows.length !== 0) {
      Saveflows.forEach((flow) => {
        if (flow.data && flow.data?.nodes)
          flow.data?.nodes.forEach((node) => {
            //looking for file fields to prevent saving the content and breaking the flow for exceeding the the data limite for local storage
            Object.keys(node.data.node.template).forEach((key) => {
              if (node.data.node.template[key].type === "file") {
                node.data.node.template[key].content = null;
                node.data.node.template[key].value = "";
              }
            });
          });
      });
      window.localStorage.setItem(
        "tabsData",
        JSON.stringify({ tabId, flows: Saveflows, id })
      );
    }
  }

  function refreshFlows() {
    getTabsDataFromDB().then((DbData) => {
      if (DbData && Object.keys(templates).length > 0) {
        try {
          processDBData(DbData);
          updateStateWithDbData(DbData);
        } catch (e) {
          console.error(e);
        }
      }
    });
  }

  useEffect(() => {
    // get data from db
    //get tabs locally saved
    // let tabsData = getLocalStorageTabsData();
    refreshFlows();
  }, [templates]);

  function getTabsDataFromDB() {
    //get tabs from db
    return readFlowsFromDatabase();
  }
  function processDBData(DbData) {
    DbData.forEach((flow) => {
      try {
        if (!flow.data) {
          return;
        }
        processFlowEdges(flow);
        processFlowNodes(flow);
      } catch (e) {
        console.error(e);
      }
    });
  }

  function processFlowEdges(flow) {
    if (!flow.data || !flow.data.edges) return;
    flow.data.edges.forEach((edge) => {
      edge.className = "";
      edge.style = { stroke: "#555" };
    });
  }

  function updateDisplay_name(node: NodeType, template: APIClassType) {
    node.data.node.display_name = template["display_name"] || node.data.type;
  }

  function updateNodeDocumentation(node: NodeType, template: APIClassType) {
    node.data.node.documentation = template["documentation"];
  }

  function processFlowNodes(flow) {
    if (!flow.data || !flow.data.nodes) return;
    flow.data.nodes.forEach((node: NodeType) => {
      const template = templates[node.data.type];
      if (!template) {
        setErrorData({ title: `Unknown node type: ${node.data.type}` });
        return;
      }
      if (Object.keys(template["template"]).length > 0) {
        updateDisplay_name(node, template);
        updateNodeBaseClasses(node, template);
        updateNodeEdges(flow, node, template);
        updateNodeDescription(node, template);
        updateNodeTemplate(node, template);
        updateNodeDocumentation(node, template);
      }
    });
  }

  function updateNodeBaseClasses(node: NodeType, template: APIClassType) {
    node.data.node.base_classes = template["base_classes"];
  }

  function updateNodeEdges(
    flow: FlowType,
    node: NodeType,
    template: APIClassType
  ) {
    flow.data.edges.forEach((edge) => {
      if (edge.source === node.id) {
        edge.sourceHandle = edge.sourceHandle
          .split("|")
          .slice(0, 2)
          .concat(template["base_classes"])
          .join("|");
      }
    });
  }

  function updateNodeDescription(node: NodeType, template: APIClassType) {
    node.data.node.description = template["description"];
  }

  function updateNodeTemplate(node: NodeType, template: APIClassType) {
    node.data.node.template = updateTemplate(
      template["template"] as unknown as APITemplateType,
      node.data.node.template as APITemplateType
    );
  }

  function updateStateWithDbData(tabsData) {
    setFlows(tabsData);
  }

  function hardReset() {
    newNodeId.current = uid();
    setTabId("");

    setFlows([]);
    setId(uid());
  }

  /**
   * Downloads the current flow as a JSON file
   */
  function downloadFlow(
    flow: FlowType,
    flowName: string,
    flowDescription?: string
  ) {
    // create a data URI with the current flow data
    const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
      JSON.stringify({ ...flow, name: flowName, description: flowDescription })
    )}`;

    // create a link element and set its properties
    const link = document.createElement("a");
    link.href = jsonString;
    link.download = `${
      flowName && flowName != ""
        ? flowName
        : flows.find((f) => f.id === tabId).name
    }.json`;

    // simulate a click on the link element to trigger the download
    link.click();
    setNoticeData({
      title: "Warning: Critical data, JSON file may include API keys.",
    });
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
  function uploadFlow(newProject?: boolean, file?: File) {
    if (file) {
      file.text().then((text) => {
        // parse the text into a JSON object
        let flow: FlowType = JSON.parse(text);

        addFlow(flow, newProject);
      });
    } else {
      // create a file input
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".json";
      // add a change event listener to the file input
      input.onchange = (e: Event) => {
        // check if the file type is application/json
        if (
          (e.target as HTMLInputElement).files[0].type === "application/json"
        ) {
          // get the file from the file input
          const currentfile = (e.target as HTMLInputElement).files[0];
          // read the file as text
          currentfile.text().then((text) => {
            // parse the text into a JSON object
            let flow: FlowType = JSON.parse(text);

            addFlow(flow, newProject);
          });
        }
      };
      // trigger the file input click event to open the file dialog
      input.click();
    }
  }

  function uploadFlows() {
    // create a file input
    const input = document.createElement("input");
    input.type = "file";
    // add a change event listener to the file input
    input.onchange = (event: Event) => {
      // check if the file type is application/json
      if (
        (event.target as HTMLInputElement).files[0].type === "application/json"
      ) {
        // get the file from the file input
        const file = (event.target as HTMLInputElement).files[0];
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
  /**
   * Add a new flow to the list of flows.
   * @param flow Optional flow to add.
   */

  function paste(
    selectionInstance,
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) {
    let minimumX = Infinity;
    let minimumY = Infinity;
    let idsMap = {};
    let nodes = reactFlowInstance.getNodes();
    let edges = reactFlowInstance.getEdges();
    selectionInstance.nodes.forEach((node) => {
      if (node.position.y < minimumY) {
        minimumY = node.position.y;
      }
      if (node.position.x < minimumX) {
        minimumX = node.position.x;
      }
    });

    const insidePosition = position.paneX
      ? { x: position.paneX + position.x, y: position.paneY + position.y }
      : reactFlowInstance.project({ x: position.x, y: position.y });

    selectionInstance.nodes.forEach((node: NodeType) => {
      // Generate a unique node ID
      let newId = getNodeId(node.data.type);
      idsMap[node.id] = newId;

      // Create a new node object
      const newNode: NodeType = {
        id: newId,
        type: "genericNode",
        position: {
          x: insidePosition.x + node.position.x - minimumX,
          y: insidePosition.y + node.position.y - minimumY,
        },
        data: {
          ..._.cloneDeep(node.data),
          id: newId,
        },
      };

      // Add the new node to the list of nodes in state
      nodes = nodes
        .map((node) => ({ ...node, selected: false }))
        .concat({ ...newNode, selected: false });
    });
    reactFlowInstance.setNodes(nodes);

    selectionInstance.edges.forEach((edge) => {
      let source = idsMap[edge.source];
      let target = idsMap[edge.target];
      let sourceHandleSplitted = edge.sourceHandle.split("|");
      let sourceHandle =
        sourceHandleSplitted[0] +
        "|" +
        source +
        "|" +
        sourceHandleSplitted.slice(2).join("|");
      let targetHandleSplitted = edge.targetHandle.split("|");
      let targetHandle =
        targetHandleSplitted.slice(0, -1).join("|") + "|" + target;
      let id =
        "reactflow__edge-" +
        source +
        sourceHandle +
        "-" +
        target +
        targetHandle;
      edges = addEdge(
        {
          source,
          target,
          sourceHandle,
          targetHandle,
          id,
          style: { stroke: "#555" },
          className:
            targetHandle.split("|")[0] === "Text"
              ? "stroke-gray-800 "
              : "stroke-gray-900 ",
          animated: targetHandle.split("|")[0] === "Text",
          selected: false,
        },
        edges.map((edge) => ({ ...edge, selected: false }))
      );
    });
    reactFlowInstance.setEdges(edges);
  }

  const addFlow = async (
    flow?: FlowType,
    newProject?: Boolean
  ): Promise<String> => {
    if (newProject) {
      let flowData = extractDataFromFlow(flow);
      if (flowData.description == "") {
        flowData.description = getRandomDescription();
      }

      // Create a new flow with a default name if no flow is provided.
      const newFlow = createNewFlow(flowData, flow);
      processFlowEdges(newFlow);
      processFlowNodes(newFlow);

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
        console.error("Error while adding flow:", error);
        throw error; // Re-throw the error so the caller can handle it if needed
      }
    } else {
      paste(
        { nodes: flow.data.nodes, edges: flow.data.edges },
        { x: 10, y: 10 }
      );
    }
  };

  const extractDataFromFlow = (flow) => {
    let data = flow?.data ? flow.data : null;
    const description = flow?.description ? flow.description : "";

    if (data) {
      updateEdges(data.edges);
      updateNodes(data.nodes, data.edges);
      updateIds(data, getNodeId); // Assuming updateIds is defined elsewhere
    }

    return { data, description };
  };

  const updateEdges = (edges) => {
    edges.forEach((edge) => {
      edge.className =
        (edge.targetHandle.split("|")[0] === "Text"
          ? "stroke-gray-800 "
          : "stroke-gray-900 ") + " stroke-connection";
      edge.animated = edge.targetHandle.split("|")[0] === "Text";
    });
  };

  const updateNodes = (nodes, edges) => {
    nodes.forEach((node) => {
      const template = templates[node.data.type];
      if (!template) {
        setErrorData({ title: `Unknown node type: ${node.data.type}` });
        return;
      }
      if (Object.keys(template["template"]).length > 0) {
        node.data.node.base_classes = template["base_classes"];
        edges.forEach((edge) => {
          if (edge.source === node.id) {
            edge.sourceHandle = edge.sourceHandle
              .split("|")
              .slice(0, 2)
              .concat(template["base_classes"])
              .join("|");
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

  const createNewFlow = (flowData, flow) => ({
    description: flowData.description,
    name: flow?.name ?? getRandomName(),
    data: flowData.data,
    id: "",
  });

  const addFlowToLocalState = (newFlow) => {
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

  async function saveFlow(newFlow: FlowType) {
    try {
      // updates flow in db
      const updatedFlow = await updateFlowInDatabase(newFlow);
      if (updatedFlow) {
        // updates flow in state
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
        //update tabs state
        setTabsState((prev) => {
          return {
            ...prev,
            [tabId]: {
              ...prev[tabId],
              isPending: false,
            },
          };
        });
      }
    } catch (err) {
      setErrorData(err);
    }
  }

  const [isBuilt, setIsBuilt] = useState(false);

  return (
    <TabsContext.Provider
      value={{
        saveFlow,
        isBuilt,
        setIsBuilt,
        lastCopiedSelection,
        setLastCopiedSelection,
        hardReset,
        tabId,
        setTabId,
        flows,
        save,
        incrementNodeId,
        removeFlow,
        addFlow,
        updateFlow,
        downloadFlow,
        downloadFlows,
        uploadFlows,
        uploadFlow,
        getNodeId,
        tabsState,
        setTabsState,
        paste,
        getTweak,
        setTweak,
      }}
    >
      {children}
    </TabsContext.Provider>
  );
}
