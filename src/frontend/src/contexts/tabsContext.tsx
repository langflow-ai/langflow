import {
  createContext,
  useEffect,
  useState,
  useRef,
  ReactNode,
  useContext,
} from "react";
import { FlowType, NodeType } from "../types/flow";
import { LangFlowState, TabsContextType } from "../types/tabs";
import {
  normalCaseToSnakeCase,
  updateIds,
  updateObject,
  updateTemplate,
} from "../utils";
import { alertContext } from "./alertContext";
import { typesContext } from "./typesContext";
import { APITemplateType, TemplateVariableType } from "../types/api";
import { v4 as uuidv4 } from "uuid";
import { addEdge } from "reactflow";
import _ from "lodash";
import {
  readFlowsFromDatabase,
  deleteFlowFromDatabase,
} from "../controllers/API";

const TabsContextInitialValue: TabsContextType = {
  save: () => {},
  tabIndex: 0,
  setTabIndex: (index: number) => {},
  flows: [],
  removeFlow: (id: string) => {},
  addFlow: (flowData?: any) => {},
  updateFlow: (newFlow: FlowType) => {},
  incrementNodeId: () => uuidv4(),
  downloadFlow: (flow: FlowType) => {},
  uploadFlow: () => {},
  hardReset: () => {},
  disableCopyPaste: false,
  setDisableCopyPaste: (state: boolean) => {},
  getNodeId: () => "",
  paste: (
    selection: { nodes: any; edges: any },
    position: { x: number; y: number }
  ) => {},
};

export const TabsContext = createContext<TabsContextType>(
  TabsContextInitialValue
);

export function TabsProvider({ children }: { children: ReactNode }) {
  const { setErrorData, setNoticeData } = useContext(alertContext);
  const [tabIndex, setTabIndex] = useState(0);
  const [flows, setFlows] = useState<Array<FlowType>>([]);
  const [id, setId] = useState(uuidv4());
  const { templates, reactFlowInstance } = useContext(typesContext);

  const newNodeId = useRef(uuidv4());
  function incrementNodeId() {
    newNodeId.current = uuidv4();
    return newNodeId.current;
  }
  function save() {
    // added clone deep to avoid mutating the original object
    let Saveflows = _.cloneDeep(flows);
    if (Saveflows.length !== 0) {
      Saveflows.forEach((flow) => {
        if (flow.data && flow.data?.nodes)
          flow.data?.nodes.forEach((node) => {
            console.log(node.data.type);
            //looking for file fields to prevent saving the content and breaking the flow for exceeding the the data limite for local storage
            Object.keys(node.data.node.template).forEach((key) => {
              console.log(node.data.node.template[key].type);
              if (node.data.node.template[key].type === "file") {
                console.log(node.data.node.template[key]);
                node.data.node.template[key].content = null;
                node.data.node.template[key].value = "";
              }
            });
          });
      });
      window.localStorage.setItem(
        "tabsData",
        JSON.stringify({ tabIndex, flows: Saveflows, id })
      );
    }
  }

  // function loadCookie(cookie: string) {
  //   if (cookie && Object.keys(templates).length > 0) {
  //     let cookieObject: LangFlowState = JSON.parse(cookie);
  //     try {
  //       cookieObject.flows.forEach((flow) => {
  //         if (!flow.data) {
  //           return;
  //         }
  //         flow.data.edges.forEach((edge) => {
  //           edge.className = "";
  //           edge.style = { stroke: "#555555" };
  //         });

  //         flow.data.nodes.forEach((node) => {
  //           const template = templates[node.data.type];
  //           if (!template) {
  //             setErrorData({ title: `Unknown node type: ${node.data.type}` });
  //             return;
  //           }
  //           if (Object.keys(template["template"]).length > 0) {
  //             node.data.node.base_classes = template["base_classes"];
  //             flow.data.edges.forEach((edge) => {
  //               if (edge.source === node.id) {
  //                 edge.sourceHandle = edge.sourceHandle
  //                   .split("|")
  //                   .slice(0, 2)
  //                   .concat(template["base_classes"])
  //                   .join("|");
  //               }
  //             });
  //             node.data.node.description = template["description"];
  //             node.data.node.template = updateTemplate(
  //               template["template"] as unknown as APITemplateType,
  //               node.data.node.template as APITemplateType
  //             );
  //           }
  //         });
  //       });
  //       setTabIndex(cookieObject.tabIndex);
  //       setFlows(cookieObject.flows);
  //       setId(cookieObject.id);
  //     } catch (e) {
  //       console.log(e);
  //     }
  //   }
  // }

  useEffect(() => {
    // get data from db
    //get tabs locally saved
    // let tabsData = getLocalStorageTabsData();
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
  }, [templates]);

  function getLocalStorageTabsData() {
    let cookie = window.localStorage.getItem("tabsData");
    let cookieObject: LangFlowState = JSON.parse(cookie);
    return cookieObject;
  }

  function getTabsDataFromDB() {
    //get tabs from db
    return readFlowsFromDatabase();
  }
  function processDBData(DbData) {
    DbData.forEach((flow) => {
      if (!flow.data) {
        return;
      }
      processFlowEdges(flow.data.edges);
      processFlowNodes(flow.data.nodes);
    });
  }
  function processTabsData(tabsData) {
    tabsData.flows.forEach((flow) => {
      if (!flow.data) {
        return;
      }
      processFlowEdges(flow.data.edges);
      processFlowNodes(flow.data.nodes);
    });
  }

  function processFlowEdges(edges) {
    edges.forEach((edge) => {
      edge.className = "";
      edge.style = { stroke: "#555555" };
    });
  }

  function processFlowNodes(nodes) {
    nodes.forEach((node) => {
      const template = templates[node.data.type];
      if (!template) {
        setErrorData({ title: `Unknown node type: ${node.data.type}` });
        return;
      }
      if (Object.keys(template["template"]).length > 0) {
        updateNodeBaseClasses(node, template);
        updateNodeEdges(node, template);
        updateNodeDescription(node, template);
        updateNodeTemplate(node, template);
      }
    });
  }

  function updateNodeBaseClasses(node, template) {
    node.data.node.base_classes = template["base_classes"];
  }

  function updateNodeEdges(node, template) {
    node.data.edges.forEach((edge) => {
      if (edge.source === node.id) {
        edge.sourceHandle = edge.sourceHandle
          .split("|")
          .slice(0, 2)
          .concat(template["base_classes"])
          .join("|");
      }
    });
  }

  function updateNodeDescription(node, template) {
    node.data.node.description = template["description"];
  }

  function updateNodeTemplate(node, template) {
    node.data.node.template = updateTemplate(
      template["template"] as unknown as APITemplateType,
      node.data.node.template as APITemplateType
    );
  }

  function updateStateWithTabsData(tabsData) {
    setTabIndex(tabsData.tabIndex);
    setFlows(tabsData.flows);
    setId(tabsData.id);
  }

  function updateStateWithDbData(tabsData) {
    setFlows(tabsData);
  }

  useEffect(() => {
    //save tabs locally
    console.log(id);
    save();
  }, [flows, id, tabIndex, newNodeId]);

  function hardReset() {
    newNodeId.current = uuidv4();
    setTabIndex(0);
    setFlows([]);
    setId(uuidv4());
  }

  /**
   * Downloads the current flow as a JSON file
   */
  function downloadFlow(flow: FlowType) {
    // create a data URI with the current flow data
    const jsonString = `data:text/json;chatset=utf-8,${encodeURIComponent(
      JSON.stringify(flow)
    )}`;

    // create a link element and set its properties
    const link = document.createElement("a");
    link.href = jsonString;
    link.download = `${flows[tabIndex].name}.json`;

    // simulate a click on the link element to trigger the download
    link.click();
    setNoticeData({
      title: "Warning: Critical data,JSON file may including API keys.",
    });
  }

  function getNodeId() {
    return `dndnode_` + incrementNodeId();
  }

  /**
   * Creates a file input and listens to a change event to upload a JSON flow file.
   * If the file type is application/json, the file is read and parsed into a JSON object.
   * The resulting JSON object is passed to the addFlow function.
   */
  function uploadFlow() {
    // create a file input
    const input = document.createElement("input");
    input.type = "file";
    // add a change event listener to the file input
    input.onchange = (e: Event) => {
      // check if the file type is application/json
      if ((e.target as HTMLInputElement).files[0].type === "application/json") {
        // get the file from the file input
        const file = (e.target as HTMLInputElement).files[0];
        // read the file as text
        file.text().then((text) => {
          // parse the text into a JSON object
          let flow: FlowType = JSON.parse(text);

          addFlow(flow);
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
    setFlows((prevState) => {
      const newFlows = [...prevState];
      const index = newFlows.findIndex((flow) => flow.id === id);
      if (index >= 0) {
        deleteFlowFromDatabase(id).then(() => {
          if (index === tabIndex) {
            setTabIndex(flows.length - 2);
            newFlows.splice(index, 1);
          } else {
            let flowId = flows[tabIndex].id;
            newFlows.splice(index, 1);
            setTabIndex(newFlows.findIndex((flow) => flow.id === flowId));
          }
        });
      }
      return newFlows;
    });
  }
  /**
   * Add a new flow to the list of flows.
   * @param flow Optional flow to add.
   */

  function paste(selectionInstance, position) {
    let minimumX = Infinity;
    let minimumY = Infinity;
    let idsMap = {};
    let nodes = reactFlowInstance.getNodes();
    let edges = reactFlowInstance.getEdges();
    selectionInstance.nodes.forEach((n) => {
      if (n.position.y < minimumY) {
        minimumY = n.position.y;
      }
      if (n.position.x < minimumX) {
        minimumX = n.position.x;
      }
    });

    const insidePosition = reactFlowInstance.project(position);

    selectionInstance.nodes.forEach((n) => {
      // Generate a unique node ID
      let newId = getNodeId();
      idsMap[n.id] = newId;

      // Create a new node object
      const newNode: NodeType = {
        id: newId,
        type: "genericNode",
        position: {
          x: insidePosition.x + n.position.x - minimumX,
          y: insidePosition.y + n.position.y - minimumY,
        },
        data: {
          ...n.data,
          id: newId,
        },
      };

      // Add the new node to the list of nodes in state
      nodes = nodes
        .map((e) => ({ ...e, selected: false }))
        .concat({ ...newNode, selected: false });
    });
    reactFlowInstance.setNodes(nodes);

    selectionInstance.edges.forEach((e) => {
      let source = idsMap[e.source];
      let target = idsMap[e.target];
      let sourceHandleSplitted = e.sourceHandle.split("|");
      let sourceHandle =
        sourceHandleSplitted[0] +
        "|" +
        source +
        "|" +
        sourceHandleSplitted.slice(2).join("|");
      let targetHandleSplitted = e.targetHandle.split("|");
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
          style: { stroke: "inherit" },
          className:
            targetHandle.split("|")[0] === "Text"
              ? "stroke-gray-800 dark:stroke-gray-300"
              : "stroke-gray-900 dark:stroke-gray-200",
          animated: targetHandle.split("|")[0] === "Text",
          selected: false,
        },
        edges.map((e) => ({ ...e, selected: false }))
      );
    });
    reactFlowInstance.setEdges(edges);
  }

  const addFlow = (flow?: FlowType) => {
    let flowData = extractDataFromFlow(flow);

    // Create a new flow with a default name if no flow is provided.
    const newFlow = createNewFlow(flowData, flow);

    // Increment the ID counter.
    setId(uuidv4());

    // Add the new flow to the list of flows.
    addFlowToLocalState(newFlow);

    // Set the tab index to the new flow.
    setTabIndexToLocalState();
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
      edge.style = { stroke: "inherit" };
      edge.className =
        edge.targetHandle.split("|")[0] === "Text"
          ? "stroke-gray-800 dark:stroke-gray-300"
          : "stroke-gray-900 dark:stroke-gray-200";
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
    name: flow?.name ?? "New Flow",
    id: uuidv4(),
    data: flowData.data,
  });

  const addFlowToLocalState = (newFlow) => {
    setFlows((prevState) => {
      return [...prevState, newFlow];
    });
  };

  const setTabIndexToLocalState = () => {
    setTabIndex(flows.length);
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

  const [disableCopyPaste, setDisableCopyPaste] = useState(false);

  return (
    <TabsContext.Provider
      value={{
        disableCopyPaste,
        setDisableCopyPaste,
        save,
        hardReset,
        tabIndex,
        setTabIndex,
        flows,
        incrementNodeId,
        removeFlow,
        addFlow,
        updateFlow,
        downloadFlow,
        uploadFlow,
        getNodeId,
        paste,
      }}
    >
      {children}
    </TabsContext.Provider>
  );
}
