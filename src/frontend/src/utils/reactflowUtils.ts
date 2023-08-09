import _ from "lodash";
import { Connection, Edge, ReactFlowInstance } from "reactflow";
import { APITemplateType } from "../types/api";
import { FlowType, NodeType } from "../types/flow";
import { cleanEdgesType } from "../types/utils/reactflowUtils";
import { toNormalCase } from "./utils";

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
        const field = targetHandle.split("|")[1];
        const id =
          (targetNode.data.node.template[field]?.input_types?.join(";") ??
            targetNode.data.node.template[field]?.type) +
          "|" +
          field +
          "|" +
          targetNode.data.id;
        if (id !== targetHandle) {
          newEdges = newEdges.filter((e) => e.id !== edge.id);
        }
      }
      if (sourceHandle) {
        const id = [
          sourceNode.data.type,
          sourceNode.data.id,
          ...sourceNode.data.node.base_classes,
        ].join("|");
        if (id !== sourceHandle) {
          newEdges = newEdges.filter((edg) => edg.id !== edge.id);
        }
      }
    }
  });
  updateEdge(newEdges);
}

export function isValidConnection(
  { source, target, sourceHandle, targetHandle }: Connection,
  reactFlowInstance: ReactFlowInstance
) {
  if (
    targetHandle
      .split("|")[0]
      .split(";")
      .some((target) => target === sourceHandle.split("|")[0]) ||
    sourceHandle
      .split("|")
      .slice(2)
      .some((target) =>
        targetHandle
          .split("|")[0]
          .split(";")
          .some((n) => n === target)
      ) ||
    targetHandle.split("|")[0] === "str"
  ) {
    let targetNode = reactFlowInstance?.getNode(target)?.data?.node;
    if (!targetNode) {
      if (
        !reactFlowInstance
          .getEdges()
          .find((e) => e.targetHandle === targetHandle)
      ) {
        return true;
      }
    } else if (
      (!targetNode.template[targetHandle.split("|")[1]].list &&
        !reactFlowInstance
          .getEdges()
          .find((e) => e.targetHandle === targetHandle)) ||
      targetNode.template[targetHandle.split("|")[1]].list
    ) {
      return true;
    }
  }
  return false;
}

export function removeApiKeys(flow: FlowType): FlowType {
  let cleanFLow = _.cloneDeep(flow);
  cleanFLow.data.nodes.forEach((node) => {
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

export function updateIds(newFlow, getNodeId) {
  let idsMap = {};

  newFlow.nodes.forEach((node: NodeType) => {
    // Generate a unique node ID
    let newId = getNodeId(node.data.type);
    idsMap[node.id] = newId;
    node.id = newId;
    node.data.id = newId;
    // Add the new node to the list of nodes in state
  });

  newFlow.edges.forEach((edge) => {
    edge.source = idsMap[edge.source];
    edge.target = idsMap[edge.target];
    let sourceHandleSplitted = edge.sourceHandle.split("|");
    edge.sourceHandle =
      sourceHandleSplitted[0] +
      "|" +
      edge.source +
      "|" +
      sourceHandleSplitted.slice(2).join("|");
    let targetHandleSplitted = edge.targetHandle.split("|");
    edge.targetHandle =
      targetHandleSplitted.slice(0, -1).join("|") + "|" + edge.target;
    edge.id =
      "reactflow__edge-" +
      edge.source +
      edge.sourceHandle +
      "-" +
      edge.target +
      edge.targetHandle;
  });
}

export function buildTweaks(flow) {
  return flow.data.nodes.reduce((acc, node) => {
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
                edge.targetHandle.split("|")[1] === t &&
                edge.targetHandle.split("|")[2] === node.id
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

export function getConnectedNodes(
  edge: Edge,
  nodes: Array<NodeType>
): Array<NodeType> {
  const sourceId = edge.source;
  const targetId = edge.target;
  return nodes.filter((node) => node.id === targetId || node.id === sourceId);
}
