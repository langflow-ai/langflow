import { cloneDeep } from "lodash";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { Edge, Node, ReactFlowInstance, addEdge } from "reactflow";
import { tweakType } from "../types/components";
import {
  FlowManagerContextType,
  FlowPoolType,
} from "../types/contexts/flowManager";
import {
  FlowType,
  NodeDataType,
  NodeType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import { buildVertices } from "../utils/buildUtils";
import {
  isInputNode,
  isOutputNode,
  scapeJSONParse,
  scapedJSONStringfy,
} from "../utils/reactflowUtils";
import { FlowsContext } from "./flowsContext";

const initialValue: FlowManagerContextType = {
  downloadFlow: (flow: FlowType) => {},
  deleteEdge: () => {},
  deleteNode: () => {},
  reactFlowInstance: null,
  setReactFlowInstance: (newState: ReactFlowInstance) => {},
  flowPool: {},
  updateFlowPoolNodes: (nodes: NodeType[]) => {},
  addDataToFlowPool: (data: any, nodeId: string) => {},
  checkInputandOutput: (flow?: FlowType) => false,
  getInputTypes: (flow?: FlowType) => [],
  getOutputTypes: (flow?: FlowType) => [],
  getInputIds: (flow?: FlowType) => [],
  getOutputIds: (flow?: FlowType) => [],
  setFilterEdge: (filter) => {},
  getFilterEdge: [],
  paste: (
    selection: { nodes: any; edges: any },
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) => {},
  setTweak: (tweak: any) => {},
  getTweak: [],
  isBuilt: false,
  setIsBuilt: (state: boolean) => {},
  inputTypes: [],
  outputTypes: [],
  inputIds: [],
  outputIds: [],
  showPanel: false,
  updateNodeFlowData: (nodeId: string, newData: NodeDataType) => {},
  buildFlow: () => new Promise(() => {}),
  setFlow: (flow: FlowType) => {},
};

export const flowManagerContext = createContext(initialValue);

export default function FlowManagerProvider({ children }) {
  const [flowPool, setFlowPool] = useState<FlowPoolType>({});
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance | null>(null);
  const [getFilterEdge, setFilterEdge] = useState([]);
  const [getTweak, setTweak] = useState<tweakType>([]);
  const { getNodeId, flows, selectedFlowId } = useContext(FlowsContext);
  const [isBuilt, setIsBuilt] = useState(false);
  const [outputTypes, setOutputTypes] = useState<string[]>([]);
  const [inputTypes, setInputTypes] = useState<string[]>([]);
  const [inputIds, setInputIds] = useState<string[]>([]);
  const [outputIds, setOutputIds] = useState<string[]>([]);
  const [showPanel, setShowPanel] = useState(false);
  const actualFlow = useRef<FlowType | null>(null);

  useEffect(() => {
    if (checkInputandOutput()) {
      setShowPanel(true);
    }
  }, [inputIds, outputIds, setShowPanel]);

  function updateFlowPoolNodes(nodes: NodeType[]) {
    //this function will update the removing the old ones
    const nodeIdsSet = new Set(nodes.map((node) => node.id));
    setFlowPool((oldFlowPool) => {
      let newFlowPool = cloneDeep({ ...oldFlowPool });
      Object.keys(newFlowPool).forEach((nodeId) => {
        if (!nodeIdsSet.has(nodeId)) {
          delete newFlowPool[nodeId];
        }
      });
      return newFlowPool;
    });
  }

  function addDataToFlowPool(data: any, nodeId: string) {
    setFlowPool((oldFlowPool) => {
      let newFlowPool = cloneDeep({ ...oldFlowPool });
      if (!newFlowPool[nodeId]) newFlowPool[nodeId] = [data];
      else {
        newFlowPool[nodeId].push(data);
      }
      return newFlowPool;
    });
  }

  function updateNodeFlowData(nodeId: string, newData: NodeDataType) {
    let oldNodes = reactFlowInstance?.getNodes();
    let targetNode = oldNodes?.find((node) => node.id === nodeId);
    if (targetNode) {
      targetNode.data = cloneDeep(newData);
      reactFlowInstance?.setNodes([...oldNodes!]);
    }
  }

  function checkInputandOutput(flow?: FlowType): boolean {
    let has_input = false;
    let has_output = false;
    if (!flow && !reactFlowInstance) {
      return false;
    }
    const nodes = flow?.data?.nodes
      ? flow.data.nodes
      : reactFlowInstance!.getNodes();
    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isInputNode(nodeData)) {
        has_input = true;
      }
      if (isOutputNode(nodeData)) {
        has_output = true;
      }
    });
    return has_input && has_output;
  }

  function getInputTypes(flow?: FlowType) {
    let inputType: string[] = [];
    if (!flow && !reactFlowInstance) {
      return [];
    }
    const nodes = flow?.data?.nodes
      ? flow.data.nodes
      : reactFlowInstance!.getNodes();
    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isInputNode(nodeData)) {
        // TODO remove count and ramdom key from type before pushing
        inputType.push(nodeData.type);
      }
    });
    setInputTypes(inputType);
    return inputType;
  }

  function getOutputTypes(flow?: FlowType) {
    let outputType: string[] = [];
    if (!flow && !reactFlowInstance) {
      return [];
    }
    const nodes = flow?.data?.nodes
      ? flow.data.nodes
      : reactFlowInstance!.getNodes();
    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isOutputNode(nodeData)) {
        // TODO remove count and ramdom key from type before pushing
        outputType.push(nodeData.type);
      }
    });
    setOutputTypes(outputType);
    return outputType;
  }

  function getInputIds(flow?: FlowType) {
    let inputIds: string[] = [];
    if (!flow && !reactFlowInstance) {
      return [];
    }
    const nodes = flow?.data?.nodes
      ? flow.data.nodes
      : reactFlowInstance!.getNodes();
    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isInputNode(nodeData)) {
        inputIds.push(nodeData.id);
      }
    });
    setInputIds(inputIds);
    return inputIds;
  }

  function getOutputIds(flow?: FlowType) {
    let outputIds: string[] = [];
    if (!flow && !reactFlowInstance) {
      return [];
    }
    const nodes = flow?.data?.nodes
      ? flow.data.nodes
      : reactFlowInstance!.getNodes();

    nodes.forEach((node) => {
      const nodeData: NodeDataType = node.data as NodeDataType;
      if (isOutputNode(nodeData)) {
        outputIds.push(nodeData.id);
      }
    });
    setOutputIds(outputIds);
    return outputIds;
  }

  function setFlow(flow: FlowType) {
    actualFlow.current = flow;
  }

  async function buildFlow() {
    function handleBuildUpdate(data: any) {
      addDataToFlowPool(data.data[data.id], data.id);
    }
    return buildVertices({
      flow: actualFlow.current!,
      onBuildUpdate: handleBuildUpdate,
    });
  }

  function deleteNode(idx: string | Array<string>) {
    reactFlowInstance!.setNodes(
      reactFlowInstance!
        .getNodes()
        .filter((node: Node) =>
          typeof idx === "string" ? node.id !== idx : !idx.includes(node.id)
        )
    );
    reactFlowInstance!.setEdges(
      reactFlowInstance!
        .getEdges()
        .filter((edge) =>
          typeof idx === "string"
            ? edge.source !== idx && edge.target !== idx
            : !idx.includes(edge.source) && !idx.includes(edge.target)
        )
    );
  }

  /**
   * Add a new flow to the list of flows.
   * @param flow Optional flow to add.
   */
  function paste(
    selectionInstance: { nodes: Node[]; edges: Edge[] },
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) {
    let minimumX = Infinity;
    let minimumY = Infinity;
    let idsMap = {};
    let nodes: Node<NodeDataType>[] = reactFlowInstance!.getNodes();
    let edges = reactFlowInstance!.getEdges();
    selectionInstance.nodes.forEach((node: Node) => {
      if (node.position.y < minimumY) {
        minimumY = node.position.y;
      }
      if (node.position.x < minimumX) {
        minimumX = node.position.x;
      }
    });

    const insidePosition = position.paneX
      ? { x: position.paneX + position.x, y: position.paneY! + position.y }
      : reactFlowInstance!.project({ x: position.x, y: position.y });

    selectionInstance.nodes.forEach((node: NodeType) => {
      // Generate a unique node ID
      let newId = getNodeId(node.data.type);
      idsMap[node.id] = newId;

      // Create a new node object
      const newNode: NodeType = {
        id: newId,
        type: "genericNode",
        position: {
          x: insidePosition.x + node.position!.x - minimumX,
          y: insidePosition.y + node.position!.y - minimumY,
        },
        data: {
          ...cloneDeep(node.data),
          id: newId,
        },
      };

      // Add the new node to the list of nodes in state
      nodes = nodes
        .map((node) => ({ ...node, selected: false }))
        .concat({ ...newNode, selected: false });
    });
    reactFlowInstance!.setNodes(nodes);

    selectionInstance.edges.forEach((edge: Edge) => {
      let source = idsMap[edge.source];
      let target = idsMap[edge.target];
      const sourceHandleObject: sourceHandleType = scapeJSONParse(
        edge.sourceHandle!
      );
      let sourceHandle = scapedJSONStringfy({
        ...sourceHandleObject,
        id: source,
      });
      sourceHandleObject.id = source;

      edge.data.sourceHandle = sourceHandleObject;
      const targetHandleObject: targetHandleType = scapeJSONParse(
        edge.targetHandle!
      );
      let targetHandle = scapedJSONStringfy({
        ...targetHandleObject,
        id: target,
      });
      targetHandleObject.id = target;
      edge.data.targetHandle = targetHandleObject;
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
          data: cloneDeep(edge.data),
          style: { stroke: "#555" },
          className:
            targetHandleObject.type === "Text"
              ? "stroke-gray-800 "
              : "stroke-gray-900 ",
          animated: targetHandleObject.type === "Text",
          selected: false,
        },
        edges.map((edge) => ({ ...edge, selected: false }))
      );
    });
    reactFlowInstance!.setEdges(edges);
  }

  function deleteEdge(idx: string | Array<string>) {
    reactFlowInstance!.setEdges(
      reactFlowInstance!
        .getEdges()
        .filter((edge: Edge) =>
          typeof idx === "string" ? edge.id !== idx : !idx.includes(edge.id)
        )
    );
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
    link.download = `${flowName && flowName != "" ? flowName : "flow"}.json`;

    // simulate a click on the link element to trigger the download
    link.click();
  }

  return (
    <flowManagerContext.Provider
      value={{
        setFlow,
        buildFlow,
        showPanel,
        inputIds,
        outputIds,
        outputTypes,
        inputTypes,
        isBuilt,
        setIsBuilt,
        downloadFlow,
        paste,
        reactFlowInstance,
        setReactFlowInstance,
        deleteEdge,
        deleteNode,
        flowPool,
        addDataToFlowPool,
        updateFlowPoolNodes,
        checkInputandOutput,
        getOutputTypes,
        getInputTypes,
        getInputIds,
        getOutputIds,
        getFilterEdge,
        setFilterEdge,
        getTweak,
        setTweak,
        updateNodeFlowData,
      }}
    >
      {children}
    </flowManagerContext.Provider>
  );
}
