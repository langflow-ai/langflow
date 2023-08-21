import _ from "lodash";
import {
  Connection,
  Edge,
  ReactFlowInstance,
  ReactFlowJsonObject,
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

// add comments to this function
export function isValidConnection(
  { source, target, sourceHandle, targetHandle }: Connection,
  reactFlowInstance: ReactFlowInstance
) {
  const targetHandleObject: targetHandleType = scapeJSONParse(targetHandle!);
  const sourceHandleObject: sourceHandleType = scapeJSONParse(sourceHandle!);
  console.log(sourceHandleObject, targetHandleObject);
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
        dataType: sourceNode.data.type,
        id: sourceNode.data.id,
        baseClasses: sourceNode.data.node!.base_classes,
      };
    }
    edge.sourceHandle = scapedJSONStringfy(newSource!);
    edge.targetHandle = scapedJSONStringfy(newTarget!);
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
  return JSON.parse(json.replace(/œ/g, '"'));
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
