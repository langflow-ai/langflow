import _ from "lodash";
import {
  Connection,
  Edge,
  Node,
  OnSelectionChangeParams,
  ReactFlowInstance,
  ReactFlowJsonObject,
  XYPosition,
} from "reactflow";
import { specialCharsRegex } from "../constants/constants";
import { APITemplateType } from "../types/api";
import {
  FlowType,
  NodeType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import {
  cleanEdgesType,
  findLastNodeType,
  generateFlowType,
  unselectAllNodesType,
  updateEdgesHandleIdsType,
} from "../types/utils/reactflowUtils";
import { toNormalCase } from "./utils";
import ShortUniqueId from "short-unique-id";
const uid = new ShortUniqueId({ length: 5 });

export function cleanEdges({
  flow: { edges, nodes },
  updateEdge,
}: cleanEdgesType) {
  let newEdges = _.cloneDeep(edges);
  edges.forEach((edge) => {
    // check if the source and target node still exists
    const sourceNode = nodes.find((node) => node.id === edge.source);
    const targetNode = nodes.find((node) => node.id === edge.target);
    if (!sourceNode || !targetNode) {
      newEdges = newEdges.filter((edg) => edg.id !== edge.id);
    }
    // check if the source and target handle still exists
    if (sourceNode && targetNode) {
      const sourceHandle = edge.sourceHandle; //right
      const targetHandle = edge.targetHandle; //left
      if (targetHandle) {
        const targetHandleObject: targetHandleType =
          scapeJSONParse(targetHandle);
        const field = targetHandleObject.fieldName;
        const id: targetHandleType = {
          type: targetNode.data.node!.template[field]?.type,
          fieldName: field,
          id: targetNode.data.id,
          inputTypes: targetNode.data.node!.template[field]?.input_types,
        };
        if (scapedJSONStringfy(id) !== targetHandle) {
          newEdges = newEdges.filter((e) => e.id !== edge.id);
        }
      }
      if (sourceHandle) {
        const id: sourceHandleType = {
          id: sourceNode.data.id,
          baseClasses: sourceNode.data.node!.base_classes,
          dataType: sourceNode.data.type,
        };
        if (scapedJSONStringfy(id) !== sourceHandle) {
          newEdges = newEdges.filter((e) => e.id !== edge.id);
        }
      }
    }
  });
  updateEdge(newEdges);
}

export function unselectAllNodes({ updateNodes, data }: unselectAllNodesType) {
  let newNodes = _.cloneDeep(data);
  newNodes!.forEach((node: Node) => {
    node.selected = false;
  });
  updateNodes(newNodes!);
}

export function isValidConnection(
  { source, target, sourceHandle, targetHandle }: Connection,
  reactFlowInstance: ReactFlowInstance
) {
  const targetHandleObject: targetHandleType = scapeJSONParse(targetHandle!);
  const sourceHandleObject: sourceHandleType = scapeJSONParse(sourceHandle!);
  if (
    targetHandleObject.inputTypes?.some(
      (n) => n === sourceHandleObject.dataType
    ) ||
    sourceHandleObject.baseClasses.some(
      (t) =>
        targetHandleObject.inputTypes?.some((n) => n === t) ||
        t === targetHandleObject.type
    ) ||
    targetHandleObject.type === "str"
  ) {
    let targetNode = reactFlowInstance?.getNode(target!)?.data?.node;
    if (!targetNode) {
      if (
        !reactFlowInstance
          .getEdges()
          .find((e) => e.targetHandle === targetHandle)
      ) {
        return true;
      }
    } else if (
      (!targetNode.template[targetHandleObject.fieldName].list &&
        !reactFlowInstance
          .getEdges()
          .find((e) => e.targetHandle === targetHandle)) ||
      targetNode.template[targetHandleObject.fieldName].list
    ) {
      return true;
    }
  }
  return false;
}

export function removeApiKeys(flow: FlowType): FlowType {
  let cleanFLow = _.cloneDeep(flow);
  cleanFLow.data!.nodes.forEach((node) => {
    for (const key in node.data.node.template) {
      if (node.data.node.template[key].password) {
        node.data.node.template[key].value = "";
      }
    }
  });
  return cleanFLow;
}

export function updateTemplate(
  reference: APITemplateType,
  objectToUpdate: APITemplateType
): APITemplateType {
  let clonedObject: APITemplateType = _.cloneDeep(reference);

  // Loop through each key in the reference object
  for (const key in clonedObject) {
    // If the key is not in the object to update, add it
    if (objectToUpdate[key] && objectToUpdate[key].value) {
      clonedObject[key].value = objectToUpdate[key].value;
    }
    if (
      objectToUpdate[key] &&
      objectToUpdate[key].advanced !== null &&
      objectToUpdate[key].advanced !== undefined
    ) {
      clonedObject[key].advanced = objectToUpdate[key].advanced;
    }
  }
  return clonedObject;
}

export function updateIds(
  newFlow: ReactFlowJsonObject,
  getNodeId: (type: string) => string
) {
  let idsMap = {};

  newFlow.nodes.forEach((node: NodeType) => {
    // Generate a unique node ID
    let newId = getNodeId(node.data.type);
    idsMap[node.id] = newId;
    node.id = newId;
    node.data.id = newId;
    // Add the new node to the list of nodes in state
  });

  newFlow.edges.forEach((edge: Edge) => {
    edge.source = idsMap[edge.source];
    edge.target = idsMap[edge.target];
    const sourceHandleObject: sourceHandleType = scapeJSONParse(
      edge.sourceHandle!
    );
    edge.sourceHandle = scapedJSONStringfy({
      ...sourceHandleObject,
      id: edge.source,
    });
    const targetHandleObject: targetHandleType = scapeJSONParse(
      edge.targetHandle!
    );
    edge.targetHandle = scapedJSONStringfy({
      ...targetHandleObject,
      id: edge.target,
    });
    edge.id =
      "reactflow__edge-" +
      edge.source +
      edge.sourceHandle +
      "-" +
      edge.target +
      edge.targetHandle;
  });
}

export function buildTweaks(flow: FlowType) {
  return flow.data!.nodes.reduce((acc, node) => {
    acc[node.data.id] = {};
    return acc;
  }, {});
}

export function validateNode(
  node: NodeType,
  reactFlowInstance: ReactFlowInstance
): Array<string> {
  if (!node.data?.node?.template || !Object.keys(node.data.node.template)) {
    return [
      "We've noticed a potential issue with a node in the flow. Please review it and, if necessary, submit a bug report with your exported flow file. Thank you for your help!",
    ];
  }

  const {
    type,
    node: { template },
  } = node.data;

  return Object.keys(template).reduce(
    (errors: Array<string>, t) =>
      errors.concat(
        template[t].required &&
          template[t].show &&
          (template[t].value === undefined ||
            template[t].value === null ||
            template[t].value === "") &&
          !reactFlowInstance
            .getEdges()
            .some(
              (edge) =>
                (scapeJSONParse(edge.targetHandle!) as targetHandleType)
                  .fieldName === t &&
                (scapeJSONParse(edge.targetHandle!) as targetHandleType).id ===
                  node.id
            )
          ? [
              `${type} is missing ${
                template.display_name || toNormalCase(template[t].name)
              }.`,
            ]
          : []
      ),
    [] as string[]
  );
}

export function validateNodes(reactFlowInstance: ReactFlowInstance) {
  if (reactFlowInstance.getNodes().length === 0) {
    return [
      "No nodes found in the flow. Please add at least one node to the flow.",
    ];
  }
  return reactFlowInstance
    .getNodes()
    .flatMap((n: NodeType) => validateNode(n, reactFlowInstance));
}

export function addVersionToDuplicates(flow: FlowType, flows: FlowType[]) {
  const existingNames = flows.map((item) => item.name);
  let newName = flow.name;
  let count = 1;

  while (existingNames.includes(newName)) {
    newName = `${flow.name} (${count})`;
    count++;
  }

  return newName;
}

export function updateEdgesHandleIds({
  edges,
  nodes,
}: updateEdgesHandleIdsType): Edge[] {
  let newEdges = _.cloneDeep(edges);
  newEdges.forEach((edge) => {
    const sourceNodeId = edge.source;
    const targetNodeId = edge.target;
    const sourceNode = nodes.find((node) => node.id === sourceNodeId);
    const targetNode = nodes.find((node) => node.id === targetNodeId);
    let source = edge.sourceHandle;
    let target = edge.targetHandle;
    //right
    let newSource: sourceHandleType;
    //left
    let newTarget: targetHandleType;
    if (target && targetNode) {
      let field = target.split("|")[1];
      newTarget = {
        type: targetNode.data.node!.template[field].type,
        fieldName: field,
        id: targetNode.data.id,
        inputTypes: targetNode.data.node!.template[field].input_types,
      };
    }
    if (source && sourceNode) {
      newSource = {
        id: sourceNode.data.id,
        baseClasses: sourceNode.data.node!.base_classes,
        dataType: sourceNode.data.type,
      };
    }
    edge.sourceHandle = scapedJSONStringfy(newSource!);
    edge.targetHandle = scapedJSONStringfy(newTarget!);
    const newData = {
      sourceHandle: scapeJSONParse(edge.sourceHandle),
      targetHandle: scapeJSONParse(edge.targetHandle),
    };
    edge.data = newData;
  });
  return newEdges;
}

export function handleKeyDown(
  e: React.KeyboardEvent<HTMLInputElement>,
  inputValue: string | string[] | null,
  block: string
) {
  //condition to fix bug control+backspace on Windows/Linux
  if (
    (typeof inputValue === "string" &&
      (e.metaKey === true || e.ctrlKey === true) &&
      e.key === "Backspace" &&
      (inputValue === block ||
        inputValue?.charAt(inputValue?.length - 1) === " " ||
        specialCharsRegex.test(inputValue?.charAt(inputValue?.length - 1)))) ||
    (navigator.userAgent.toUpperCase().includes("MAC") &&
      e.ctrlKey === true &&
      e.key === "Backspace")
  ) {
    e.preventDefault();
    e.stopPropagation();
  }

  if (e.ctrlKey === true && e.key === "Backspace" && inputValue === block) {
    e.preventDefault();
    e.stopPropagation();
  }
}

export function getConnectedNodes(
  edge: Edge,
  nodes: Array<NodeType>
): Array<NodeType> {
  const sourceId = edge.source;
  const targetId = edge.target;
  return nodes.filter((node) => node.id === targetId || node.id === sourceId);
}

export function scapedJSONStringfy(json: object): string {
  return customStringify(json).replace(/"/g, "œ");
}
export function scapeJSONParse(json: string): any {
  let parsed = json.replace(/œ/g, '"');
  return JSON.parse(parsed);
}

// this function receives an array of edges and return true if any of the handles are not a json string
export function checkOldEdgesHandles(edges: Edge[]): boolean {
  return edges.some(
    (edge) =>
      !edge.sourceHandle ||
      !edge.targetHandle ||
      !edge.sourceHandle.includes("{") ||
      !edge.targetHandle.includes("{")
  );
}

export function customStringify(obj: any): string {
  if (typeof obj === "undefined") {
    return "null";
  }

  if (obj === null || typeof obj !== "object") {
    if (obj instanceof Date) {
      return `"${obj.toISOString()}"`;
    }
    return JSON.stringify(obj);
  }

  if (Array.isArray(obj)) {
    const arrayItems = obj.map((item) => customStringify(item)).join(",");
    return `[${arrayItems}]`;
  }

  const keys = Object.keys(obj).sort();
  const keyValuePairs = keys.map(
    (key) => `"${key}":${customStringify(obj[key])}`
  );
  return `{${keyValuePairs.join(",")}}`;
}

export function getMiddlePoint(nodes: Node[]) {
  let middlePointX = 0;
  let middlePointY = 0;

  nodes.forEach((node) => {
    middlePointX += node.position.x;
    middlePointY += node.position.y;
  });

  const totalNodes = nodes.length;
  const averageX = middlePointX / totalNodes;
  const averageY = middlePointY / totalNodes;

  return { x: averageX, y: averageY };
}

export function generateFlow(
  selection: OnSelectionChangeParams,
  reactFlowInstance: ReactFlowInstance,
  name: string
): generateFlowType {
  const newFlowData = reactFlowInstance.toObject();

  /*	remove edges that are not connected to selected nodes on both ends
		in future we can save this edges to when ungrouping reconect to the old nodes
	*/
  newFlowData.edges = selection.edges.filter(
    (edge) =>
      selection.nodes.some((node) => node.id === edge.target) &&
      selection.nodes.some((node) => node.id === edge.source)
  );
  newFlowData.nodes = selection.nodes;

  const newFlow: FlowType = {
    data: newFlowData,
    name: name,
    description: "",
    //generating local id instead of using the id from the server, can change in the future
    id: uid(),
  };
  // filter edges that are not connected to selected nodes on both ends
  // using O(n²) aproach because the number of edges is small
  // in the future we can use a better aproach using a set
  return {
    newFlow,
    removedEdges: selection.edges.filter(
      (edge) => !newFlowData.edges.includes(edge)
    ),
  };
}

export function filterFlow(
  selection: OnSelectionChangeParams,
  reactFlowInstance: ReactFlowInstance
) {
  reactFlowInstance.setNodes((nodes) =>
    nodes.filter((node) => !selection.nodes.includes(node))
  );
  reactFlowInstance.setEdges((edges) =>
    edges.filter((edge) => !selection.edges.includes(edge))
  );
}

export function findLastNode({
  nodes,
  edges,
}: findLastNodeType) {
  /*
		this function receives a flow and return the last node
	*/
  let lastNode = nodes.find((n) => !edges.some((e) => e.source === n.id));
  return lastNode;
}

export function updateFlowPosition(NewPosition: XYPosition, flow: FlowType) {
  const middlePoint = getMiddlePoint(flow.data!.nodes);
  let deltaPosition = {
    x: NewPosition.x - middlePoint.x,
    y: NewPosition.y - middlePoint.y,
  };
  flow.data!.nodes.forEach((node) => {
    node.position.x += deltaPosition.x;
    node.position.y += deltaPosition.y;
  });
}

export function concatFlows(
  flow: FlowType,
  ReactFlowInstance: ReactFlowInstance
) {
  const { nodes, edges } = flow.data!;
  ReactFlowInstance.addNodes(nodes);
  ReactFlowInstance.addEdges(edges);
}

export function generateNodeFromFlow(flow: FlowType): NodeType {
  const { nodes } = flow.data!;
  const outputNode = _.cloneDeep(findLastNode(flow.data!));
  // console.log(flow)
  const position = getMiddlePoint(nodes);
  let data = _.cloneDeep(flow);
  const newGroupNode: NodeType = {
    data: {
      id: data.id,
      type: outputNode!.data.type,
      node: {
        display_name:"group Node",
        documentation: "",
        base_classes: outputNode!.data.node!.base_classes,
        description: "group Node",
        template: generateNodeTemplate(data),
        flow: data,
      },
    },
    id: data.id,
    position,
    type: "groupNode",
  };
  return newGroupNode;
}