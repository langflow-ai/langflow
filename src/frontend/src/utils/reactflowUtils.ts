import _ from "lodash";
import { Connection, Edge, ReactFlowInstance } from "reactflow";
import { APITemplateType } from "../types/api";
import {
  FlowType,
  NodeType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import {
  cleanEdgesType,
  updateEdgesHandleIdsType,
} from "../types/utils/reactflowUtils";
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
      newEdges = newEdges.filter((e) => e.id !== edge.id);
    }
    // check if the source and target handle still exists
    if (sourceNode && targetNode) {
      const sourceHandle = edge.sourceHandle; //right
      const targetHandle = edge.targetHandle; //left
      if (targetHandle) {
        const targetHandleObject: targetHandleType = JSON.parse(targetHandle);
        const field = targetHandleObject.fieldName;
        const id: targetHandleType = {
          type: targetNode.data.node.template[field]?.type,
          fieldName: field,
          id: targetNode.data.id,
          inputTypes: targetNode.data.node.template[field]?.input_types,
        };
        if (JSON.stringify(id) !== targetHandle) {
          newEdges = newEdges.filter((e) => e.id !== edge.id);
        }
      }
      if (sourceHandle) {
        const id: sourceHandleType = {
          id: sourceNode.data.id,
          baseClasses: sourceNode.data.node.base_classes,
          dataType: sourceNode.data.type,
        };
        if (JSON.stringify(id) !== sourceHandle) {
          newEdges = newEdges.filter((e) => e.id !== edge.id);
        }
      }
    }
  });
  updateEdge(newEdges);
}

// add comments to this function
export function isValidConnection(
  { source, target, sourceHandle, targetHandle }: Connection,
  reactFlowInstance: ReactFlowInstance
) {
  const targetHandleObject: targetHandleType = JSON.parse(targetHandle);
  const sourceHandleObject: sourceHandleType = JSON.parse(sourceHandle);
  if (
    targetHandleObject.inputTypes?.some(
      (n) => n === sourceHandleObject.dataType
    ) ||
    sourceHandleObject.baseClasses.some((t) =>
      targetHandleObject.inputTypes?.some((n) => n === t)
    ) ||
    targetHandleObject.type === "str"
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

  newFlow.nodes.forEach((n: NodeType) => {
    // Generate a unique node ID
    let newId = getNodeId(n.data.type);
    idsMap[n.id] = newId;
    n.id = newId;
    n.data.id = newId;
    // Add the new node to the list of nodes in state
  });

  newFlow.edges.forEach((e: Edge) => {
    e.source = idsMap[e.source];
    e.target = idsMap[e.target];
    const sourceHandleObject: sourceHandleType = JSON.parse(e.sourceHandle);
    e.sourceHandle = JSON.stringify({ ...sourceHandleObject, id: e.source });
    const targetHandleObject: targetHandleType = JSON.parse(e.targetHandle);
    e.targetHandle = JSON.stringify({ ...targetHandleObject, id: e.target });
    e.id =
      "reactflow__edge-" +
      e.source +
      e.sourceHandle +
      "-" +
      e.target +
      e.targetHandle;
  });
}

export function buildTweaks(flow) {
  return flow.data.nodes.reduce((acc, node) => {
    acc[node.data.id] = {};
    return acc;
  }, {});
}

export function validateNode(
  n: NodeType,
  reactFlowInstance: ReactFlowInstance
): Array<string> {
  if (!n.data?.node?.template || !Object.keys(n.data.node.template)) {
    return [
      "We've noticed a potential issue with a node in the flow. Please review it and, if necessary, submit a bug report with your exported flow file. Thank you for your help!",
    ];
  }

  const {
    type,
    node: { template },
  } = n.data;

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
              (e) =>
                e.targetHandle.split("|")[1] === t &&
                e.targetHandle.split("|")[2] === n.id
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
  setEdges,
}: updateEdgesHandleIdsType) {
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
        type: targetNode.data.node.template[field].type,
        fieldName: field,
        id: targetNode.data.id,
        inputTypes: targetNode.data.node.template[field].input_types,
      };
    }
    if (source && sourceNode) {
      newSource = {
        dataType: sourceNode.data.type,
        id: sourceNode.data.id,
        baseClasses: sourceNode.data.node.base_classes,
      };
    }
    edge.sourceHandle = JSON.stringify(newSource);
    edge.targetHandle = JSON.stringify(newTarget);
  });
  setEdges(newEdges);
}
