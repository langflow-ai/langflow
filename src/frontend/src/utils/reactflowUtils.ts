/**
 * In Honor of Otávio Anovazzi (@anovazzi1)
 *
 * This file contains the highest number of commits by Otávio in the entire Langflow project,
 * reflecting his unmatched dedication, expertise, and innovative spirit. Each line of code
 * is a testament to his relentless pursuit of excellence and his significant impact on this
 * project's evolution.

 * His commitment to selflessly helping others embodies the true meaning of open source,
 * and his legacy lives on in each one of his 2771 contributions, inspiring us to build exceptional
 * software for all.
 */

import {
  getLeftHandleId,
  getRightHandleId,
} from "@/CustomNodes/utils/get-handle-id";
import { INCOMPLETE_LOOP_ERROR_ALERT } from "@/constants/alerts_constants";
import { customDownloadFlow } from "@/customization/utils/custom-reactFlowUtils";
import useFlowStore from "@/stores/flowStore";
import {
  Connection,
  Edge,
  getOutgoers,
  Node,
  OnSelectionChangeParams,
  ReactFlowJsonObject,
  XYPosition,
} from "@xyflow/react";
import { cloneDeep } from "lodash";
import ShortUniqueId from "short-unique-id";
import getFieldTitle from "../CustomNodes/utils/get-field-title";
import {
  INPUT_TYPES,
  IS_MAC,
  LANGFLOW_SUPPORTED_TYPES,
  OUTPUT_TYPES,
  specialCharsRegex,
  SUCCESS_BUILD,
} from "../constants/constants";
import { DESCRIPTIONS } from "../flow_constants";
import {
  APIClassType,
  APIKindType,
  APIObjectType,
  APITemplateType,
  InputFieldType,
  OutputFieldType,
} from "../types/api";
import {
  AllNodeType,
  EdgeType,
  FlowType,
  NodeDataType,
  sourceHandleType,
  targetHandleType,
} from "../types/flow";
import {
  addEscapedHandleIdsToEdgesType,
  findLastNodeType,
  generateFlowType,
  updateEdgesHandleIdsType,
} from "../types/utils/reactflowUtils";
import { getLayoutedNodes } from "./layoutUtils";
import { createRandomKey, toTitleCase } from "./utils";
const uid = new ShortUniqueId();

export function checkChatInput(nodes: Node[]) {
  return nodes.some((node) => node.data.type === "ChatInput");
}

export function checkWebhookInput(nodes: Node[]) {
  return nodes.some((node) => node.data.type === "Webhook");
}

export function cleanEdges(nodes: AllNodeType[], edges: EdgeType[]) {
  let newEdges: EdgeType[] = cloneDeep(
    edges.map((edge) => ({ ...edge, selected: false, animated: false })),
  );
  edges.forEach((edge) => {
    // check if the source and target node still exists
    const sourceNode = nodes.find((node) => node.id === edge.source);
    const targetNode = nodes.find((node) => node.id === edge.target);
    if (!sourceNode || !targetNode) {
      newEdges = newEdges.filter((edg) => edg.id !== edge.id);
      return;
    }
    // check if the source and target handle still exists
    const sourceHandle = edge.sourceHandle; //right
    const targetHandle = edge.targetHandle; //left
    if (targetHandle) {
      const targetHandleObject: targetHandleType = scapeJSONParse(targetHandle);
      const field = targetHandleObject.fieldName;
      let id: targetHandleType | sourceHandleType;

      const templateFieldType = targetNode.data.node!.template[field]?.type;
      const inputTypes = targetNode.data.node!.template[field]?.input_types;
      const hasProxy = targetNode.data.node!.template[field]?.proxy;
      const isToolMode = targetNode.data.node!.template[field]?.tool_mode;

      if (
        !field &&
        targetHandleObject.name &&
        targetNode.type === "genericNode"
      ) {
        const dataType = targetNode.data.type;
        const outputTypes =
          targetNode.data.node!.outputs?.find(
            (output) => output.name === targetHandleObject.name,
          )?.types ?? [];

        id = {
          dataType: dataType ?? "",
          name: targetHandleObject.name,
          id: targetNode.data.id,
          output_types: outputTypes,
        };
      } else {
        id = {
          type: templateFieldType,
          fieldName: field,
          id: targetNode.data.id,
          inputTypes: inputTypes,
        };
        if (hasProxy) {
          id.proxy = targetNode.data.node!.template[field]?.proxy;
        }
      }
      if (
        scapedJSONStringfy(id) !== targetHandle ||
        (targetNode.data.node?.tool_mode && isToolMode)
      ) {
        newEdges = newEdges.filter((e) => e.id !== edge.id);
      }
    }
    if (sourceHandle) {
      const parsedSourceHandle = scapeJSONParse(sourceHandle);
      const name = parsedSourceHandle.name;

      if (sourceNode.type == "genericNode") {
        const output = sourceNode.data
          .node!.outputs?.filter((output) => output.selected)
          .find((output) => output.name === name);

        if (output) {
          const outputTypes =
            output!.types.length === 1 ? output!.types : [output!.selected!];

          const id: sourceHandleType = {
            id: sourceNode.data.id,
            name: name,
            output_types: outputTypes,
            dataType: sourceNode.data.type,
          };

          if (scapedJSONStringfy(id) !== sourceHandle) {
            newEdges = newEdges.filter((e) => e.id !== edge.id);
          }
        } else {
          newEdges = newEdges.filter((e) => e.id !== edge.id);
        }
      }
    }

    newEdges = filterHiddenFieldsEdges(edge, newEdges, targetNode);
  });
  return newEdges;
}

export function filterHiddenFieldsEdges(
  edge: EdgeType,
  newEdges: EdgeType[],
  targetNode: AllNodeType,
) {
  if (targetNode) {
    const targetHandle = edge.data?.targetHandle;
    if (!targetHandle) return newEdges;

    const fieldName = targetHandle.fieldName;
    const nodeTemplates = targetNode.data.node!.template;

    // Only check the specific field the edge is connected to
    if (nodeTemplates[fieldName]?.show === false) {
      newEdges = newEdges.filter((e) => e.id !== edge.id);
    }
  }
  return newEdges;
}

export function detectBrokenEdgesEdges(nodes: AllNodeType[], edges: Edge[]) {
  function generateAlertObject(sourceNode, targetNode, edge) {
    const targetHandleObject: targetHandleType = scapeJSONParse(
      edge.targetHandle,
    );
    const sourceHandleObject: sourceHandleType = scapeJSONParse(
      edge.sourceHandle,
    );
    const name = sourceHandleObject.name;
    const output = sourceNode.data.node!.outputs?.find(
      (output) => output.name === name,
    );

    return {
      source: {
        nodeDisplayName: sourceNode.data.node!.display_name,
        outputDisplayName: output?.display_name,
      },
      target: {
        displayName: targetNode.data.node!.display_name,
        field:
          targetNode.data.node!.template[targetHandleObject.fieldName]
            ?.display_name ??
          targetHandleObject.fieldName ??
          targetHandleObject.name,
      },
    };
  }
  let newEdges = cloneDeep(edges);
  let BrokenEdges: {
    source: {
      nodeDisplayName: string;
      outputDisplayName?: string;
    };
    target: {
      displayName: string;
      field: string;
    };
  }[] = [];
  edges.forEach((edge) => {
    // check if the source and target node still exists
    const sourceNode = nodes.find((node) => node.id === edge.source);
    const targetNode = nodes.find((node) => node.id === edge.target);
    if (!sourceNode || !targetNode) {
      newEdges = newEdges.filter((edg) => edg.id !== edge.id);
      return;
    }
    // check if the source and target handle still exists
    const sourceHandle = edge.sourceHandle; //right
    const targetHandle = edge.targetHandle; //left
    if (targetHandle) {
      const targetHandleObject: targetHandleType = scapeJSONParse(targetHandle);
      const field = targetHandleObject.fieldName;
      let id: sourceHandleType | targetHandleType;

      const templateFieldType = targetNode.data.node!.template[field]?.type;
      const inputTypes = targetNode.data.node!.template[field]?.input_types;
      const hasProxy = targetNode.data.node!.template[field]?.proxy;

      if (
        !field &&
        targetHandleObject.name &&
        targetNode.type === "genericNode"
      ) {
        const dataType = targetNode.data.type;
        const outputTypes =
          targetNode.data.node!.outputs?.find(
            (output) => output.name === targetHandleObject.name,
          )?.types ?? [];

        id = {
          dataType: dataType ?? "",
          name: targetHandleObject.name,
          id: targetNode.data.id,
          output_types: outputTypes,
        };
      } else {
        id = {
          type: templateFieldType,
          fieldName: field,
          id: targetNode.data.id,
          inputTypes: inputTypes,
        };
        if (hasProxy) {
          id.proxy = targetNode.data.node!.template[field]?.proxy;
        }
      }
      if (scapedJSONStringfy(id) !== targetHandle) {
        newEdges = newEdges.filter((e) => e.id !== edge.id);
        BrokenEdges.push(generateAlertObject(sourceNode, targetNode, edge));
      }
    }
    if (sourceHandle) {
      const parsedSourceHandle = scapeJSONParse(sourceHandle);
      const name = parsedSourceHandle.name;
      if (sourceNode.type == "genericNode") {
        const output = sourceNode.data.node!.outputs?.find(
          (output) => output.name === name,
        );
        if (output) {
          const outputTypes =
            output!.types.length === 1 ? output!.types : [output!.selected!];

          const id: sourceHandleType = {
            id: sourceNode.data.id,
            name: name,
            output_types: outputTypes,
            dataType: sourceNode.data.type,
          };
          if (scapedJSONStringfy(id) !== sourceHandle) {
            newEdges = newEdges.filter((e) => e.id !== edge.id);
            BrokenEdges.push(generateAlertObject(sourceNode, targetNode, edge));
          }
        } else {
          newEdges = newEdges.filter((e) => e.id !== edge.id);
          BrokenEdges.push(generateAlertObject(sourceNode, targetNode, edge));
        }
      }
    }
  });
  return BrokenEdges;
}

export function unselectAllNodesEdges(nodes: Node[], edges: Edge[]) {
  nodes.forEach((node: Node) => {
    node.selected = false;
  });
  edges.forEach((edge: Edge) => {
    edge.selected = false;
  });
}

export function isValidConnection(
  connection: Connection,
  nodes?: AllNodeType[],
  edges?: EdgeType[],
): boolean {
  const { source, target, sourceHandle, targetHandle } = connection;
  if (source === target) {
    return false;
  }

  const nodesArray = nodes || useFlowStore.getState().nodes;
  const edgesArray = edges || useFlowStore.getState().edges;

  const targetHandleObject: targetHandleType = scapeJSONParse(targetHandle!);
  const sourceHandleObject: sourceHandleType = scapeJSONParse(sourceHandle!);

  // Helper to find the edge between two nodes
  function findEdgeBetween(srcId: string, tgtId: string) {
    return edgesArray.find((e) => e.source === srcId && e.target === tgtId);
  }

  // Modified hasCycle to return the path of edges forming the loop
  const findCyclePath = (
    node: AllNodeType,
    visited = new Set(),
    path: EdgeType[] = [],
  ): EdgeType[] | null => {
    if (visited.has(node.id)) return null;
    visited.add(node.id);
    for (const outgoer of getOutgoers(node, nodesArray, edgesArray)) {
      const edge = findEdgeBetween(node.id, outgoer.id);
      if (!edge) continue;
      if (outgoer.id === source) {
        // This edge would close the loop
        return [...path, edge];
      }
      const result = findCyclePath(outgoer, visited, [...path, edge]);
      if (result) return result;
    }
    return null;
  };

  if (
    targetHandleObject.inputTypes?.some(
      (n) => n === sourceHandleObject.dataType,
    ) ||
    (targetHandleObject.output_types &&
      (targetHandleObject.output_types?.some(
        (n) => n === sourceHandleObject.dataType,
      ) ||
        sourceHandleObject.output_types.some((t) =>
          targetHandleObject.output_types?.some((n) => n === t),
        ))) ||
    sourceHandleObject.output_types.some(
      (t) =>
        targetHandleObject.inputTypes?.some((n) => n === t) ||
        t === targetHandleObject.type,
    )
  ) {
    let targetNode = nodesArray.find((node) => node.id === target!);
    let targetNodeDataNode = targetNode?.data?.node;
    if (
      (!targetNodeDataNode &&
        !edgesArray.find((e) => e.targetHandle === targetHandle)) ||
      (targetNodeDataNode &&
        targetHandleObject.output_types &&
        !edgesArray.find((e) => e.targetHandle === targetHandle)) ||
      (targetNodeDataNode &&
        !targetHandleObject.output_types &&
        ((!targetNodeDataNode.template[targetHandleObject.fieldName].list &&
          !edgesArray.find((e) => e.targetHandle === targetHandle)) ||
          targetNodeDataNode.template[targetHandleObject.fieldName].list))
    ) {
      // If the current target handle is a loop component, allow connection immediately
      if (targetHandleObject.output_types) {
        return true;
      }
      // Check for loop and if any edge in the loop is a loop component
      let cyclePath: EdgeType[] | null = null;
      if (targetNode) {
        cyclePath = findCyclePath(targetNode);
      }
      if (cyclePath) {
        // Check if any edge in the cycle path is a loop component
        const hasLoopComponent = cyclePath.some((edge) => {
          try {
            const th = scapeJSONParse(edge.targetHandle!);
            return !!th.output_types;
          } catch {
            return false;
          }
        });
        if (!hasLoopComponent) {
          return false;
        }
      }
      return true;
    }
  }
  return false;
}

export function removeApiKeys(flow: FlowType): FlowType {
  let cleanFLow = cloneDeep(flow);
  cleanFLow.data!.nodes.forEach((node) => {
    if (node.type !== "genericNode") return;
    for (const key in node.data.node!.template) {
      if (node.data.node!.template[key].password) {
        node.data.node!.template[key].value = "";
      }
    }
  });
  return cleanFLow;
}

export function updateTemplate(
  reference: APITemplateType,
  objectToUpdate: APITemplateType,
): APITemplateType {
  let clonedObject: APITemplateType = cloneDeep(reference);

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

export const processFlows = (DbData: FlowType[], skipUpdate = true) => {
  let savedComponents: { [key: string]: APIClassType } = {};
  DbData.forEach(async (flow: FlowType) => {
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
            uid.randomUUID(5),
          )
        ] = cloneDeep((flow.data.nodes[0].data as NodeDataType).node!);
        return;
      }
      await processDataFromFlow(flow, !skipUpdate).catch((e) => {
        console.error(e);
      });
    } catch (e) {
      console.error(e);
    }
  });
  return { data: savedComponents, flows: DbData };
};

export const needsLayout = (nodes: AllNodeType[]) => {
  return nodes.some((node) => !node.position);
};

export async function processDataFromFlow(
  flow: FlowType,
  refreshIds = true,
): Promise<ReactFlowJsonObject<AllNodeType, EdgeType> | null> {
  let data = flow?.data ? flow.data : null;
  if (data) {
    processFlowEdges(flow);
    //add dropdown option to nodeOutputs
    processFlowNodes(flow);
    //add animation to text type edges
    updateEdges(data.edges);
    // updateNodes(data.nodes, data.edges);
    if (refreshIds) updateIds(data); // Assuming updateIds is defined elsewhere
    // add layout to nodes if not present
    if (needsLayout(data.nodes)) {
      const layoutedNodes = await getLayoutedNodes(data.nodes, data.edges);
      data.nodes = layoutedNodes;
    }
  }
  return data;
}

export function updateIds(
  { edges, nodes }: { edges: EdgeType[]; nodes: AllNodeType[] },
  selection?: OnSelectionChangeParams,
) {
  let idsMap = {};
  const selectionIds = selection?.nodes.map((n) => n.id);
  if (nodes) {
    nodes.forEach((node: AllNodeType) => {
      // Generate a unique node ID
      let newId = getNodeId(node.data.type);
      if (selection && !selectionIds?.includes(node.id)) {
        newId = node.id;
      }
      idsMap[node.id] = newId;
      node.id = newId;
      node.data.id = newId;
      // Add the new node to the list of nodes in state
    });
    selection?.nodes.forEach((sNode: Node) => {
      if (sNode.type === "genericNode") {
        let newId = idsMap[sNode.id];
        sNode.id = newId;
        sNode.data.id = newId;
      }
    });
  }
  const concatedEdges = [...edges, ...((selection?.edges as EdgeType[]) ?? [])];
  if (concatedEdges)
    concatedEdges.forEach((edge: EdgeType) => {
      edge.source = idsMap[edge.source];
      edge.target = idsMap[edge.target];

      const sourceHandleObject: sourceHandleType = scapeJSONParse(
        edge.sourceHandle!,
      );
      edge.sourceHandle = scapedJSONStringfy({
        ...sourceHandleObject,
        id: edge.source,
      });
      if (edge.data?.sourceHandle?.id) {
        edge.data.sourceHandle.id = edge.source;
      }
      const targetHandleObject: targetHandleType = scapeJSONParse(
        edge.targetHandle!,
      );
      edge.targetHandle = scapedJSONStringfy({
        ...targetHandleObject,
        id: edge.target,
      });
      if (edge.data?.targetHandle?.id) {
        edge.data.targetHandle.id = edge.target;
      }
      edge.id =
        "reactflow__edge-" +
        edge.source +
        edge.sourceHandle +
        "-" +
        edge.target +
        edge.targetHandle;
    });
  return idsMap;
}

export function validateNode(node: AllNodeType, edges: Edge[]): Array<string> {
  if (!node.data?.node?.template || !Object.keys(node.data.node.template)) {
    return [
      "We've noticed a potential issue with a Component in the flow. Please review it and, if necessary, submit a bug report with your exported flow file. Thank you for your help!",
    ];
  }

  const {
    type,
    node: { template },
  } = node.data;

  const displayName = node.data.node.display_name;

  return Object.keys(template).reduce((errors: Array<string>, t) => {
    if (
      node.type === "genericNode" &&
      template[t].required &&
      !(template[t].tool_mode && node?.data?.node?.tool_mode) &&
      template[t].show &&
      (template[t].value === undefined ||
        template[t].value === null ||
        template[t].value === "") &&
      !edges.some(
        (edge) =>
          (scapeJSONParse(edge.targetHandle!) as targetHandleType).fieldName ===
            t &&
          (scapeJSONParse(edge.targetHandle!) as targetHandleType).id ===
            node.id,
      )
    ) {
      errors.push(
        `${displayName || type} is missing ${getFieldTitle(template, t)}.`,
      );
    } else if (
      template[t].type === "dict" &&
      template[t].required &&
      template[t].show &&
      (template[t].value !== undefined ||
        template[t].value !== null ||
        template[t].value !== "")
    ) {
      if (hasDuplicateKeys(template[t].value))
        errors.push(
          `${displayName || type} (${getFieldTitle(
            template,
            t,
          )}) contains duplicate keys with the same values.`,
        );
      if (hasEmptyKey(template[t].value))
        errors.push(
          `${displayName || type} (${getFieldTitle(
            template,
            t,
          )}) field must not be empty.`,
        );
    }
    return errors;
  }, [] as string[]);
}

export function validateNodes(
  nodes: AllNodeType[],
  edges: EdgeType[],
): // this returns an array of tuples with the node id and the errors
Array<{ id: string; errors: Array<string> }> {
  if (nodes.length === 0) {
    return [
      {
        id: "",
        errors: [
          "No components found in the flow. Please add at least one component to the flow.",
        ],
      },
    ];
  }
  // validateNode(n, edges) returns an array of errors for the node
  const nodeMap = nodes.map((n) => ({
    id: n.id,
    errors: validateNode(n, edges),
  }));

  return nodeMap.filter((n) => n.errors?.length);
}

export function validateEdge(
  e: EdgeType,
  nodes: AllNodeType[],
  edges: EdgeType[],
): Array<string> {
  const targetHandleObject: targetHandleType = scapeJSONParse(e.targetHandle!);

  const loop = hasLoop(e, nodes, edges);
  if (targetHandleObject.output_types && !loop) {
    return [INCOMPLETE_LOOP_ERROR_ALERT];
  }
  return [];
}

function hasLoop(
  e: EdgeType,
  nodes: AllNodeType[],
  edges: EdgeType[],
): boolean {
  const source = e.source;
  const target = e.target;

  // Check if this connection would create a cycle
  const targetNode = nodes.find((n) => n.id === target);

  const hasCycle = (
    node,
    visited = new Set(),
    firstEdge: EdgeType | null = null,
  ): boolean => {
    if (visited.has(node.id)) return false;

    visited.add(node.id);

    for (const outgoer of getOutgoers(node, nodes, edges)) {
      const edge = edges.find(
        (e) => e.source === node.id && e.target === outgoer.id,
      );
      if (outgoer.id === source) {
        const sourceHandleObject = scapeJSONParse(
          firstEdge?.sourceHandle ?? edge?.sourceHandle ?? "",
        );
        const sourceHandleParsed = scapedJSONStringfy(sourceHandleObject);
        if (sourceHandleParsed === e.targetHandle) {
          return true;
        }
      }
      if (hasCycle(outgoer, visited, firstEdge || edge)) return true;
    }
    return false;
  };

  if (targetNode?.id === source) return false;
  return hasCycle(targetNode);
}

export function updateEdges(edges: EdgeType[]) {
  if (edges)
    edges.forEach((edge) => {
      const targetHandleObject: targetHandleType = scapeJSONParse(
        edge.targetHandle!,
      );
      edge.className = "";
    });
}

export function addVersionToDuplicates(flow: FlowType, flows: FlowType[]) {
  const flowsWithoutUpdatedFlow = flows.filter((f) => f.id !== flow.id);

  const existingNames = flowsWithoutUpdatedFlow.map((item) => item.name);
  let newName = flow.name;
  let count = 1;

  while (existingNames.includes(newName)) {
    newName = `${flow.name} (${count})`;
    count++;
  }

  return newName;
}

export function addEscapedHandleIdsToEdges({
  edges,
}: addEscapedHandleIdsToEdgesType): EdgeType[] {
  let newEdges = cloneDeep(edges);
  newEdges.forEach((edge) => {
    let escapedSourceHandle = edge.sourceHandle;
    let escapedTargetHandle = edge.targetHandle;
    if (!escapedSourceHandle) {
      let sourceHandle = edge.data?.sourceHandle;
      if (sourceHandle) {
        escapedSourceHandle = getRightHandleId(sourceHandle);
        edge.sourceHandle = escapedSourceHandle;
      }
    }
    if (!escapedTargetHandle) {
      let targetHandle = edge.data?.targetHandle;
      if (targetHandle) {
        escapedTargetHandle = getLeftHandleId(targetHandle);
        edge.targetHandle = escapedTargetHandle;
      }
    }
  });
  return newEdges;
}
export function updateEdgesHandleIds({
  edges,
  nodes,
}: updateEdgesHandleIdsType): EdgeType[] {
  let newEdges = cloneDeep(edges);
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
    if (source && sourceNode && sourceNode.type === "genericNode") {
      const output_types =
        sourceNode.data.node!.output_types ??
        sourceNode.data.node!.base_classes!;
      newSource = {
        id: sourceNode.data.id,
        output_types,
        dataType: sourceNode.data.type,
        name: output_types.join(" | "),
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

export function updateNewOutput({ nodes, edges }: updateEdgesHandleIdsType) {
  let newEdges = cloneDeep(edges);
  let newNodes = cloneDeep(nodes);
  newEdges.forEach((edge) => {
    if (edge.sourceHandle && edge.targetHandle) {
      let newSourceHandle: sourceHandleType = scapeJSONParse(edge.sourceHandle);
      let newTargetHandle: targetHandleType = scapeJSONParse(edge.targetHandle);
      const id = newSourceHandle.id;
      const sourceNodeIndex = newNodes.findIndex((node) => node.id === id);
      let sourceNode: AllNodeType | undefined = undefined;
      if (sourceNodeIndex !== -1) {
        sourceNode = newNodes[sourceNodeIndex];
      }
      if (sourceNode?.type === "genericNode") {
        let intersection;
        if (newSourceHandle.baseClasses) {
          if (!newSourceHandle.output_types) {
            if (sourceNode?.data.node!.output_types) {
              newSourceHandle.output_types =
                sourceNode?.data.node!.output_types;
            } else {
              newSourceHandle.output_types = newSourceHandle.baseClasses;
            }
          }
          delete newSourceHandle.baseClasses;
        }
        if (
          newTargetHandle.inputTypes &&
          newTargetHandle.inputTypes.length > 0
        ) {
          intersection = newSourceHandle.output_types.filter((type) =>
            newTargetHandle.inputTypes!.includes(type),
          );
        } else {
          intersection = newSourceHandle.output_types.filter(
            (type) => type === newTargetHandle.type,
          );
        }
        const selected = intersection[0];
        newSourceHandle.name = newSourceHandle.output_types.join(" | ");
        newSourceHandle.output_types = [selected];
        if (sourceNode) {
          if (!sourceNode.data.node?.outputs) {
            sourceNode.data.node!.outputs = [];
          }
          const types =
            sourceNode.data.node!.output_types ??
            sourceNode.data.node!.base_classes!;
          if (
            !sourceNode.data.node!.outputs.some(
              (output) => output.selected === selected,
            )
          ) {
            sourceNode.data.node!.outputs.push({
              types,
              selected: selected,
              name: types.join(" | "),
              display_name: types.join(" | "),
            });
          }
        }

        edge.sourceHandle = scapedJSONStringfy(newSourceHandle);
        if (edge.data) {
          edge.data.sourceHandle = newSourceHandle;
        }
      }
    }
  });
  return { nodes: newNodes, edges: newEdges };
}

export function handleKeyDown(
  e:
    | React.KeyboardEvent<HTMLInputElement>
    | React.KeyboardEvent<HTMLTextAreaElement>,
  inputValue: string | number | string[] | null | undefined,
  block: string,
) {
  //condition to fix bug control+backspace on Windows/Linux
  if (
    (typeof inputValue === "string" &&
      (e.metaKey === true || e.ctrlKey === true) &&
      e.key === "Backspace" &&
      (inputValue === block ||
        inputValue?.charAt(inputValue?.length - 1) === " " ||
        specialCharsRegex.test(inputValue?.charAt(inputValue?.length - 1)))) ||
    (IS_MAC && e.ctrlKey === true && e.key === "Backspace")
  ) {
    e.preventDefault();
    e.stopPropagation();
  }

  if (e.ctrlKey === true && e.key === "Backspace" && inputValue === block) {
    e.preventDefault();
    e.stopPropagation();
  }
}

export function handleOnlyIntegerInput(
  event: React.KeyboardEvent<HTMLInputElement>,
) {
  if (
    event.key === "." ||
    event.key === "-" ||
    event.key === "," ||
    event.key === "e" ||
    event.key === "E" ||
    event.key === "+"
  ) {
    event.preventDefault();
  }
}

export function getConnectedNodes(
  edge: Edge,
  nodes: Array<AllNodeType>,
): Array<AllNodeType> {
  const sourceId = edge.source;
  const targetId = edge.target;
  return nodes.filter((node) => node.id === targetId || node.id === sourceId);
}

export function convertObjToArray(singleObject: object | string, type: string) {
  if (type !== "dict") return [{ "": "" }];
  if (typeof singleObject === "string") {
    singleObject = JSON.parse(singleObject);
  }
  if (Array.isArray(singleObject)) return singleObject;

  let arrConverted: any[] = [];
  if (typeof singleObject === "object") {
    for (const key in singleObject) {
      if (Object.prototype.hasOwnProperty.call(singleObject, key)) {
        const newObj = {};
        newObj[key] = singleObject[key];
        arrConverted.push(newObj);
      }
    }
  }
  return arrConverted;
}

export function convertArrayToObj(arrayOfObjects) {
  if (!Array.isArray(arrayOfObjects)) return arrayOfObjects;

  let objConverted = {};
  for (const obj of arrayOfObjects) {
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        objConverted[key] = obj[key];
      }
    }
  }
  return objConverted;
}

export function hasDuplicateKeys(array) {
  const keys = {};
  // Transforms an empty object into an object array without opening the 'editNode' modal to prevent the flow build from breaking.
  if (!Array.isArray(array)) array = [{ "": "" }];
  for (const obj of array) {
    for (const key in obj) {
      if (keys[key]) {
        return true;
      }
      keys[key] = true;
    }
  }
  return false;
}

export function hasEmptyKey(objArray) {
  // Transforms an empty object into an array without opening the 'editNode' modal to prevent the flow build from breaking.
  if (!Array.isArray(objArray)) objArray = [];
  for (const obj of objArray) {
    for (const key in obj) {
      if (obj.hasOwnProperty(key) && key === "") {
        return true; // Found an empty key
      }
    }
  }
  return false; // No empty keys found
}

export function convertValuesToNumbers(arr) {
  return arr.map((obj) => {
    const newObj = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        let value = obj[key];
        if (/^\d+$/.test(value)) {
          value = value?.toString().trim();
        }
        newObj[key] =
          value === "" || isNaN(value) ? value.toString() : Number(value);
      }
    }
    return newObj;
  });
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
      !edge.targetHandle.includes("{"),
  );
}

export function checkEdgeWithoutEscapedHandleIds(edges: Edge[]): boolean {
  return edges.some(
    (edge) =>
      (!edge.sourceHandle || !edge.targetHandle) && edge.data?.sourceHandle,
  );
}

export function checkOldNodesOutput(nodes: AllNodeType[]): boolean {
  return nodes.some(
    (node) =>
      node.type === "genericNode" && node.data.node?.outputs === undefined,
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
    (key) => `"${key}":${customStringify(obj[key])}`,
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

export function getNodeId(nodeType: string) {
  return nodeType + "-" + uid.randomUUID(5);
}

export function getHandleId(
  source: string,
  sourceHandle: string,
  target: string,
  targetHandle: string,
) {
  return (
    "reactflow__edge-" + source + sourceHandle + "-" + target + targetHandle
  );
}

export function generateFlow(
  selection: OnSelectionChangeParams,
  nodes: AllNodeType[],
  edges: EdgeType[],
  name: string,
): generateFlowType {
  const newFlowData = { nodes, edges, viewport: { zoom: 1, x: 0, y: 0 } };
  /*	remove edges that are not connected to selected nodes on both ends
   */
  newFlowData.edges = edges.filter(
    (edge) =>
      selection.nodes.some((node) => node.id === edge.target) &&
      selection.nodes.some((node) => node.id === edge.source),
  );
  newFlowData.nodes = selection.nodes as AllNodeType[];

  const newFlow: FlowType = {
    data: newFlowData,
    is_component: false,
    name: name,
    description: "",
    //generating local id instead of using the id from the server, can change in the future
    id: uid.randomUUID(5),
  };
  // filter edges that are not connected to selected nodes on both ends
  // using O(n²) aproach because the number of edges is small
  // in the future we can use a better aproach using a set
  return {
    newFlow,
    removedEdges: edges.filter(
      (edge) =>
        (selection.nodes.some((node) => node.id === edge.target) ||
          selection.nodes.some((node) => node.id === edge.source)) &&
        newFlowData.edges.every((e) => e.id !== edge.id),
    ),
  };
}

export function reconnectEdges(
  groupNode: AllNodeType,
  excludedEdges: EdgeType[],
) {
  if (groupNode.type !== "genericNode" || !groupNode.data.node!.flow) return [];
  let newEdges = cloneDeep(excludedEdges);
  const { nodes, edges } = groupNode.data.node!.flow!.data!;
  const lastNode = findLastNode(groupNode.data.node!.flow!.data!);
  newEdges = newEdges.filter(
    (e) => !(nodes.some((n) => n.id === e.source) && e.source !== lastNode?.id),
  );
  newEdges.forEach((edge) => {
    const newSourceHandle: sourceHandleType = scapeJSONParse(
      edge.sourceHandle!,
    );
    const newTargetHandle: targetHandleType = scapeJSONParse(
      edge.targetHandle!,
    );
    if (lastNode && edge.source === lastNode.id) {
      edge.source = groupNode.id;
      newSourceHandle.id = groupNode.id;
      edge.sourceHandle = scapedJSONStringfy(newSourceHandle);
    }
    if (nodes.some((node) => node.id === edge.target)) {
      const targetNode = nodes.find((node) => node.id === edge.target)!;
      const proxy = { id: targetNode.id, field: newTargetHandle.fieldName };
      newTargetHandle.id = groupNode.id;
      newTargetHandle.proxy = proxy;
      edge.target = groupNode.id;
      newTargetHandle.fieldName =
        newTargetHandle.fieldName + "_" + targetNode.id;
      edge.targetHandle = scapedJSONStringfy(newTargetHandle);
    }
    if (newSourceHandle && newTargetHandle) {
      edge.data = {
        sourceHandle: newSourceHandle,
        targetHandle: newTargetHandle,
      };
    }
  });
  return newEdges;
}

export function filterFlow(
  selection: OnSelectionChangeParams,
  setNodes: (update: Node[] | ((oldState: Node[]) => Node[])) => void,
  setEdges: (update: Edge[] | ((oldState: Edge[]) => Edge[])) => void,
) {
  setNodes((nodes) => nodes.filter((node) => !selection.nodes.includes(node)));
  setEdges((edges) => edges.filter((edge) => !selection.edges.includes(edge)));
}

export function findLastNode({ nodes, edges }: findLastNodeType) {
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
  return {
    ...flow,
    data: {
      ...flow.data!,
      nodes: flow.data!.nodes.map((node) => ({
        ...node,
        position: {
          x: node.position.x + deltaPosition.x,
          y: node.position.y + deltaPosition.y,
        },
      })),
    },
  };
}

export function concatFlows(
  flow: FlowType,
  setNodes: (update: Node[] | ((oldState: Node[]) => Node[])) => void,
  setEdges: (update: Edge[] | ((oldState: Edge[]) => Edge[])) => void,
) {
  const { nodes, edges } = flow.data!;
  setNodes((old) => [...old, ...nodes]);
  setEdges((old) => [...old, ...edges]);
}

export function validateSelection(
  selection: OnSelectionChangeParams,
  edges: Edge[],
): Array<string> {
  const clonedSelection = cloneDeep(selection);
  const clonedEdges = cloneDeep(edges);
  //add edges to selection if selection mode selected only nodes
  if (clonedSelection.edges.length === 0) {
    clonedSelection.edges = clonedEdges;
  }

  // get only edges that are connected to the nodes in the selection
  // first creates a set of all the nodes ids
  let nodesSet = new Set(clonedSelection.nodes.map((n) => n.id));
  // then filter the edges that are connected to the nodes in the set
  let connectedEdges = clonedSelection.edges.filter(
    (e) => nodesSet.has(e.source) && nodesSet.has(e.target),
  );
  // add the edges to the selection
  clonedSelection.edges = connectedEdges;

  let errorsArray: Array<string> = [];
  // check if there is more than one node
  if (clonedSelection.nodes.length < 2) {
    errorsArray.push("Please select more than one component");
  }
  if (
    clonedSelection.nodes.some(
      (node) =>
        isInputNode(node.data as NodeDataType) ||
        isOutputNode(node.data as NodeDataType),
    )
  ) {
    errorsArray.push("Select non-input/output components only");
  }
  //check if there are two or more nodes with free outputs
  if (
    clonedSelection.nodes.filter(
      (n) => !clonedSelection.edges.some((e) => e.source === n.id),
    ).length > 1
  ) {
    errorsArray.push("Select only one component with free outputs");
  }

  // check if there is any node that does not have any connection
  if (
    clonedSelection.nodes.some(
      (node) =>
        !clonedSelection.edges.some((edge) => edge.target === node.id) &&
        !clonedSelection.edges.some((edge) => edge.source === node.id),
    )
  ) {
    errorsArray.push("Select only connected components");
  }
  return errorsArray;
}
function updateGroupNodeTemplate(template: APITemplateType) {
  /*this function receives a template, iterates for it's items
	updating the visibility of all basic types setting it to advanced true*/
  Object.keys(template).forEach((key) => {
    let type = template[key].type;
    let input_types = template[key].input_types;
    if (
      LANGFLOW_SUPPORTED_TYPES.has(type) &&
      !template[key].required &&
      !input_types
    ) {
      template[key].advanced = true;
    }
    //prevent code fields from showing on the group node
    if (type === "code" && key === "code") {
      template[key].show = false;
    }
  });
  return template;
}
export function mergeNodeTemplates({
  nodes,
  edges,
}: {
  nodes: AllNodeType[];
  edges: Edge[];
}): APITemplateType {
  /* this function receives a flow and iterate throw each node
		and merge the templates with only the visible fields
		if there are two keys with the same name in the flow, we will update the display name of each one
		to show from which node it came from
	*/
  let template: APITemplateType = {};
  nodes.forEach((node) => {
    let nodeTemplate = cloneDeep(node.data.node!.template);
    Object.keys(nodeTemplate)
      .filter((field_name) => field_name.charAt(0) !== "_")
      .forEach((key) => {
        if (
          node.type === "genericNode" &&
          !isTargetHandleConnected(edges, key, nodeTemplate[key], node.id)
        ) {
          template[key + "_" + node.id] = nodeTemplate[key];
          template[key + "_" + node.id].proxy = { id: node.id, field: key };
          if (node.data.type === "GroupNode") {
            template[key + "_" + node.id].display_name =
              node.data.node!.flow!.name + " - " + nodeTemplate[key].name;
          } else {
            template[key + "_" + node.id].display_name =
              //data id already has the node name on it
              nodeTemplate[key].display_name
                ? nodeTemplate[key].display_name
                : nodeTemplate[key].name
                  ? toTitleCase(nodeTemplate[key].name)
                  : toTitleCase(key);
          }
        }
      });
  });
  return template;
}
export function isTargetHandleConnected(
  edges: Edge[],
  key: string,
  field: InputFieldType,
  nodeId: string,
) {
  /*
		this function receives a flow and a handleId and check if there is a connection with this handle
	*/
  if (!field) return true;
  if (field.proxy) {
    if (
      edges.some(
        (e) =>
          e.targetHandle ===
          scapedJSONStringfy({
            type: field.type,
            fieldName: key,
            id: nodeId,
            proxy: { id: field.proxy!.id, field: field.proxy!.field },
            inputTypes: field.input_types,
          } as targetHandleType),
      )
    ) {
      return true;
    }
  } else {
    if (
      edges.some(
        (e) =>
          e.targetHandle ===
          scapedJSONStringfy({
            type: field.type,
            fieldName: key,
            id: nodeId,
            inputTypes: field.input_types,
          } as targetHandleType),
      )
    ) {
      return true;
    }
  }
  return false;
}

export function generateNodeTemplate(Flow: FlowType) {
  /*
		this function receives a flow and generate a template for the group node
	*/
  let template = mergeNodeTemplates({
    nodes: Flow.data!.nodes,
    edges: Flow.data!.edges,
  });
  updateGroupNodeTemplate(template);
  return template;
}

export function generateNodeFromFlow(
  flow: FlowType,
  getNodeId: (type: string) => string,
): AllNodeType {
  const { nodes } = flow.data!;
  const outputNode = cloneDeep(findLastNode(flow.data!));
  const position = getMiddlePoint(nodes);
  let data = cloneDeep(flow);
  const id = getNodeId("groupComponent");
  const newGroupNode: AllNodeType = {
    data: {
      id,
      type: "GroupNode",
      node: {
        display_name: "Group",
        documentation: "",
        description: "",
        template: generateNodeTemplate(data),
        flow: data,
        outputs: generateNodeOutputs(data),
      },
    },
    id,
    position,
    type: "genericNode",
  };
  return newGroupNode;
}

function generateNodeOutputs(flow: FlowType) {
  const { nodes, edges } = flow.data!;
  const outputs: Array<OutputFieldType> = [];
  nodes.forEach((node: AllNodeType) => {
    if (node.type === "genericNode" && node.data.node?.outputs) {
      const nodeOutputs = node.data.node.outputs;
      nodeOutputs.forEach((output) => {
        //filter outputs that are not connected
        if (
          !edges.some(
            (edge) =>
              edge.source === node.id &&
              (edge.data?.sourceHandle as sourceHandleType).name ===
                output.name,
          )
        ) {
          outputs.push(
            cloneDeep({
              ...output,
              proxy: {
                id: node.id,
                name: output.name,
                nodeDisplayName:
                  node.data.node!.display_name ?? node.data.node!.name,
              },
              name: node.id + "_" + output.name,
              display_name: output.display_name,
            }),
          );
        }
      });
    }
  });
  return outputs;
}

export function updateProxyIdsOnTemplate(
  template: APITemplateType,
  idsMap: { [key: string]: string },
) {
  Object.keys(template).forEach((key) => {
    if (template[key].proxy && idsMap[template[key].proxy!.id]) {
      template[key].proxy!.id = idsMap[template[key].proxy!.id];
    }
  });
}

export function updateProxyIdsOnOutputs(
  outputs: OutputFieldType[] | undefined,
  idsMap: { [key: string]: string },
) {
  if (!outputs) return;
  outputs.forEach((output) => {
    if (output.proxy && idsMap[output.proxy.id]) {
      output.proxy.id = idsMap[output.proxy.id];
    }
  });
}

export function updateEdgesIds(
  edges: EdgeType[],
  idsMap: { [key: string]: string },
) {
  edges.forEach((edge) => {
    let targetHandle: targetHandleType = edge.data!.targetHandle;
    if (targetHandle.proxy && idsMap[targetHandle.proxy!.id]) {
      targetHandle.proxy!.id = idsMap[targetHandle.proxy!.id];
    }
    edge.data!.targetHandle = targetHandle;
    edge.targetHandle = scapedJSONStringfy(targetHandle);
  });
}

export function processFlowEdges(flow: FlowType) {
  if (!flow.data || !flow.data.edges) return;
  if (checkEdgeWithoutEscapedHandleIds(flow.data.edges)) {
    const newEdges = addEscapedHandleIdsToEdges({ edges: flow.data.edges });
    flow.data.edges = newEdges;
  } else if (checkOldEdgesHandles(flow.data.edges)) {
    const newEdges = updateEdgesHandleIds(flow.data);
    flow.data.edges = newEdges;
  }
}

export function processFlowNodes(flow: FlowType) {
  if (!flow.data || !flow.data.nodes) return;
  if (checkOldNodesOutput(flow.data.nodes)) {
    const { nodes, edges } = updateNewOutput(flow.data);
    flow.data.nodes = nodes;
    flow.data.edges = edges;
  }
}

export function expandGroupNode(
  id: string,
  flow: FlowType,
  template: APITemplateType,
  setNodes: (
    update: AllNodeType[] | ((oldState: AllNodeType[]) => AllNodeType[]),
  ) => void,
  setEdges: (
    update: EdgeType[] | ((oldState: EdgeType[]) => EdgeType[]),
  ) => void,
  outputs?: OutputFieldType[],
) {
  const idsMap = updateIds(flow!.data!);
  updateProxyIdsOnTemplate(template, idsMap);
  let flowEdges = useFlowStore.getState().edges;
  updateEdgesIds(flowEdges, idsMap);
  const gNodes: AllNodeType[] = cloneDeep(flow?.data?.nodes!);
  const gEdges = cloneDeep(flow!.data!.edges);
  // //redirect edges to correct proxy node
  // let updatedEdges: Edge[] = [];
  // flowEdges.forEach((edge) => {
  //   let newEdge = cloneDeep(edge);
  //   if (newEdge.target === id) {
  //     const targetHandle: targetHandleType = newEdge.data.targetHandle;
  //     if (targetHandle.proxy) {
  //       let type = targetHandle.type;
  //       let field = targetHandle.proxy.field;
  //       let proxyId = targetHandle.proxy.id;
  //       let inputTypes = targetHandle.inputTypes;
  //       let node: NodeType = gNodes.find((n) => n.id === proxyId)!;
  //       if (node) {
  //         newEdge.target = proxyId;
  //         let newTargetHandle: targetHandleType = {
  //           fieldName: field,
  //           type,
  //           id: proxyId,
  //           inputTypes: inputTypes,
  //         };
  //         if (node.data.node?.flow) {
  //           newTargetHandle.proxy = {
  //             field: node.data.node.template[field].proxy?.field!,
  //             id: node.data.node.template[field].proxy?.id!,
  //           };
  //         }
  //         newEdge.data.targetHandle = newTargetHandle;
  //         newEdge.targetHandle = scapedJSONStringfy(newTargetHandle);
  //       }
  //     }
  //   }
  //   if (newEdge.source === id) {
  //     const lastNode = cloneDeep(findLastNode(flow!.data!));
  //     newEdge.source = lastNode!.id;
  //     let newSourceHandle: sourceHandleType = scapeJSONParse(
  //       newEdge.sourceHandle!,
  //     );
  //     newSourceHandle.id = lastNode!.id;
  //     newEdge.data.sourceHandle = newSourceHandle;
  //     newEdge.sourceHandle = scapedJSONStringfy(newSourceHandle);
  //   }
  //   if (edge.target === id || edge.source === id) {
  //     updatedEdges.push(newEdge);
  //   }
  // });
  //update template values
  Object.keys(template).forEach((key) => {
    if (template[key].proxy) {
      let { field, id } = template[key].proxy!;
      let nodeIndex = gNodes.findIndex((n) => n.id === id);
      if (nodeIndex !== -1) {
        let proxy: { id: string; field: string } | undefined;
        let display_name: string | undefined;
        let show = gNodes[nodeIndex].data.node!.template[field].show;
        let advanced = gNodes[nodeIndex].data.node!.template[field].advanced;
        if (gNodes[nodeIndex].data.node!.template[field].display_name) {
          display_name =
            gNodes[nodeIndex].data.node!.template[field].display_name;
        } else {
          display_name = gNodes[nodeIndex].data.node!.template[field].name;
        }
        if (gNodes[nodeIndex].data.node!.template[field].proxy) {
          proxy = gNodes[nodeIndex].data.node!.template[field].proxy;
        }
        gNodes[nodeIndex].data.node!.template[field] = template[key];
        gNodes[nodeIndex].data.node!.template[field].show = show;
        gNodes[nodeIndex].data.node!.template[field].advanced = advanced;
        gNodes[nodeIndex].data.node!.template[field].display_name =
          display_name;
        // keep the nodes selected after ungrouping
        // gNodes[nodeIndex].selected = false;
        if (proxy) {
          gNodes[nodeIndex].data.node!.template[field].proxy = proxy;
        } else {
          delete gNodes[nodeIndex].data.node!.template[field].proxy;
        }
      }
    }
  });
  outputs?.forEach((output) => {
    let nodeIndex = gNodes.findIndex((n) => n.id === output.proxy!.id);
    if (nodeIndex !== -1) {
      const node = gNodes[nodeIndex];
      if (node.type === "genericNode") {
        if (node.data.node?.outputs) {
          const nodeOutputIndex = node.data.node!.outputs!.findIndex(
            (o) => o.name === output.proxy?.name,
          );
          if (nodeOutputIndex !== -1 && output.selected) {
            node.data.node!.outputs![nodeOutputIndex].selected =
              output.selected;
          }
        }
      }
    }
  });
  const filteredNodes = [
    ...useFlowStore.getState().nodes.filter((n) => n.id !== id),
    ...gNodes,
  ];
  const filteredEdges = [
    ...flowEdges.filter((e) => e.target !== id && e.source !== id),
    ...gEdges,
  ];
  setNodes(filteredNodes);
  setEdges(filteredEdges);
}

export function getGroupStatus(
  flow: FlowType,
  ssData: { [key: string]: { valid: boolean; params: string } },
) {
  let status = { valid: true, params: SUCCESS_BUILD };
  const { nodes } = flow.data!;
  const ids = nodes.map((n: AllNodeType) => n.data.id);
  ids.forEach((id) => {
    if (!ssData[id]) {
      status = ssData[id];
      return;
    }
    if (!ssData[id].valid) {
      status = { valid: false, params: ssData[id].params };
    }
  });
  return status;
}

export function createFlowComponent(
  nodeData: NodeDataType,
  version: string,
): FlowType {
  const flowNode: FlowType = {
    data: {
      edges: [],
      nodes: [
        {
          data: { ...nodeData, node: { ...nodeData.node, official: false } },
          id: nodeData.id,
          position: { x: 0, y: 0 },
          type: "genericNode",
        },
      ],
      viewport: { x: 1, y: 1, zoom: 1 },
    },
    description: nodeData.node?.description || "",
    name: nodeData.node?.display_name || nodeData.type || "",
    id: nodeData.id || "",
    is_component: true,
    last_tested_version: version,
  };
  return flowNode;
}

export function downloadNode(NodeFLow: FlowType) {
  const element = document.createElement("a");
  const file = new Blob([JSON.stringify(NodeFLow)], {
    type: "application/json",
  });
  element.href = URL.createObjectURL(file);
  element.download = `${NodeFLow?.name ?? "node"}.json`;
  element.click();
}

export function updateComponentNameAndType(
  data: any,
  component: NodeDataType,
) {}

export function removeFileNameFromComponents(flow: FlowType) {
  flow.data!.nodes.forEach((node: AllNodeType) => {
    if (node.type === "genericNode") {
      Object.keys(node.data.node!.template).forEach((field) => {
        if (node.data.node?.template[field].type === "file") {
          node.data.node!.template[field].value = "";
        }
      });
      if (node.data.node?.flow) {
        removeFileNameFromComponents(node.data.node.flow);
      }
    }
  });
}

export function removeGlobalVariableFromComponents(flow: FlowType) {
  flow.data!.nodes.forEach((node: AllNodeType) => {
    if (node.type === "genericNode") {
      Object.keys(node.data.node!.template).forEach((field) => {
        if (node.data?.node?.template[field]?.load_from_db) {
          node.data.node!.template[field].value = "";
          node.data.node!.template[field].load_from_db = false;
        }
      });
      if (node.data.node?.flow) {
        removeGlobalVariableFromComponents(node.data.node.flow);
      }
    }
  });
}

export function typesGenerator(data: APIObjectType) {
  return Object.keys(data)
    .reverse()
    .reduce((acc, curr) => {
      Object.keys(data[curr]).forEach((c: keyof APIKindType) => {
        acc[c] = curr;
        // Add the base classes to the accumulator as well.
        data[curr][c].base_classes?.forEach((b) => {
          acc[b] = curr;
        });
      });
      return acc;
    }, {});
}

export function templatesGenerator(data: APIObjectType) {
  return Object.keys(data).reduce((acc, curr) => {
    Object.keys(data[curr]).forEach((c: keyof APIKindType) => {
      //prevent wrong overwriting of the component template by a group of the same type
      if (!data[curr][c].flow) acc[c] = data[curr][c];
    });
    return acc;
  }, {});
}

export function extractFieldsFromComponenents(data: APIObjectType) {
  const fields = new Set<string>();

  // Check if data exists
  if (!data) {
    console.warn("[Types] Data is undefined in extractFieldsFromComponenents");
    return fields;
  }

  Object.keys(data).forEach((key) => {
    // Check if data[key] exists
    if (!data[key]) {
      console.warn(
        `[Types] data["${key}"] is undefined in extractFieldsFromComponenents`,
      );
      return;
    }

    Object.keys(data[key]).forEach((kind) => {
      // Check if data[key][kind] exists
      if (!data[key][kind]) {
        console.warn(
          `[Types] data["${key}"]["${kind}"] is undefined in extractFieldsFromComponenents`,
        );
        return;
      }

      // Check if template exists
      if (!data[key][kind].template) {
        console.warn(
          `[Types] data["${key}"]["${kind}"].template is undefined in extractFieldsFromComponenents`,
        );
        return;
      }

      Object.keys(data[key][kind].template).forEach((field) => {
        if (
          data[key][kind].template[field]?.display_name &&
          data[key][kind].template[field]?.show
        )
          fields.add(data[key][kind].template[field].display_name!);
      });
    });
  });

  return fields;
}
/**
 * Recursively sorts all object keys and arrays in a JSON structure
 * @param obj - The object to sort keys and arrays for
 * @returns A new object with sorted keys and arrays
 */
function sortJsonStructure<T>(obj: T): T {
  // Handle null case
  if (obj === null) {
    return obj;
  }

  // Handle arrays - sort array elements if they are objects
  if (Array.isArray(obj)) {
    return obj.map((item) => sortJsonStructure(item)) as unknown as T;
  }

  // Only process actual objects
  if (typeof obj !== "object") {
    return obj;
  }

  // Create a new object with sorted keys
  return Object.keys(obj)
    .sort()
    .reduce((result, key) => {
      // Recursively sort nested objects and arrays
      result[key] = sortJsonStructure(obj[key]);
      return result;
    }, {} as any);
}

/**
 * Downloads the flow as a JSON file with sorted keys and arrays
 * @param flow - The flow to download
 * @param flowName - The name to use for the flow
 * @param flowDescription - Optional description for the flow
 */
export async function downloadFlow(
  flow: FlowType,
  flowName: string,
  flowDescription?: string,
) {
  try {
    const clonedFlow = cloneDeep(flow);

    removeFileNameFromComponents(clonedFlow);

    const flowData = {
      ...clonedFlow,
      name: flowName,
      description: flowDescription,
    };

    const sortedData = sortJsonStructure(flowData);
    const sortedJsonString = JSON.stringify(sortedData, null, 2);

    customDownloadFlow(flow, sortedJsonString, flowName);
  } catch (error) {
    console.error("Error downloading flow:", error);
  }
}

export function getRandomElement<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)];
}

export function getRandomDescription(): string {
  return getRandomElement(DESCRIPTIONS);
}

export const createNewFlow = (
  flowData: ReactFlowJsonObject<AllNodeType, EdgeType>,
  folderId: string,
  flow?: FlowType,
) => {
  return {
    description: flow?.description ?? getRandomDescription(),
    name: flow?.name ? flow.name : "Untitled document",
    data: flowData,
    id: "",
    icon: flow?.icon ?? undefined,
    gradient: flow?.gradient ?? undefined,
    is_component: flow?.is_component ?? false,
    folder_id: folderId,
    endpoint_name: flow?.endpoint_name ?? undefined,
    tags: flow?.tags ?? [],
    mcp_enabled: true,
  };
};

export function isInputNode(nodeData: NodeDataType): boolean {
  return INPUT_TYPES.has(nodeData.type);
}

export function isOutputNode(nodeData: NodeDataType): boolean {
  return OUTPUT_TYPES.has(nodeData.type);
}

export function isInputType(type: string): boolean {
  return INPUT_TYPES.has(type);
}

export function isOutputType(type: string): boolean {
  return OUTPUT_TYPES.has(type);
}

export function updateGroupRecursion(
  groupNode: AllNodeType,
  edges: EdgeType[],
  unavailableFields:
    | {
        [name: string]: string;
      }
    | undefined,
  globalVariablesEntries: string[] | undefined,
) {
  if (groupNode.type === "genericNode") {
    updateGlobalVariables(
      groupNode.data.node,
      unavailableFields,
      globalVariablesEntries,
    );
    if (groupNode.data.node?.flow) {
      groupNode.data.node.flow.data!.nodes.forEach((node) => {
        if (node.type === "genericNode") {
          if (node.data.node?.flow) {
            updateGroupRecursion(
              node,
              node.data.node.flow.data!.edges,
              unavailableFields,
              globalVariablesEntries,
            );
          }
        }
      });
      let newFlow = groupNode.data.node!.flow;
      const idsMap = updateIds(newFlow.data!);
      updateProxyIdsOnTemplate(groupNode.data.node!.template, idsMap);
      updateProxyIdsOnOutputs(groupNode.data.node.outputs, idsMap);
      let flowEdges = edges;
      updateEdgesIds(flowEdges, idsMap);
    }
  }
}
export function updateGlobalVariables(
  node: APIClassType | undefined,
  unavailableFields:
    | {
        [name: string]: string;
      }
    | undefined,
  globalVariablesEntries: string[] | undefined,
) {
  if (node && node.template) {
    Object.keys(node.template).forEach((field) => {
      if (
        globalVariablesEntries &&
        node!.template[field].load_from_db &&
        !globalVariablesEntries.includes(node!.template[field].value)
      ) {
        node!.template[field].value = "";
        node!.template[field].load_from_db = false;
      }
      if (
        !node!.template[field].load_from_db &&
        node!.template[field].value === "" &&
        unavailableFields &&
        Object.keys(unavailableFields).includes(
          node!.template[field].display_name ?? "",
        )
      ) {
        node!.template[field].value =
          unavailableFields[node!.template[field].display_name ?? ""];
        node!.template[field].load_from_db = true;
      }
    });
  }
}

export function getGroupOutputNodeId(
  flow: FlowType,
  p_name: string,
  p_node_id: string,
) {
  let node: AllNodeType | undefined = flow.data?.nodes.find(
    (n) => n.id === p_node_id,
  );
  if (!node || node.type !== "genericNode") return;
  if (node.data.node?.flow) {
    let output = node.data.node.outputs?.find((o) => o.name === p_name);
    if (output && output.proxy) {
      return getGroupOutputNodeId(
        node.data.node.flow,
        output.proxy.name,
        output.proxy.id,
      );
    }
  }
  return { id: node.id, outputName: p_name };
}

export function checkOldComponents({ nodes }: { nodes: any[] }) {
  return nodes.some(
    (node) =>
      node.data.node?.template.code &&
      (node.data.node?.template.code.value as string).includes(
        "(CustomComponent):",
      ),
  );
}

export function someFlowTemplateFields(
  { nodes }: { nodes: AllNodeType[] },
  validateFn: (field: InputFieldType) => boolean,
): boolean {
  return nodes.some((node) => {
    return Object.keys(node.data.node?.template ?? {}).some((field) => {
      return validateFn((node.data.node?.template ?? {})[field]);
    });
  });
}

/**
 * Determines if the provided API template supports tool mode.
 *
 * A template is considered to support tool mode if either:
 * - It contains only the 'code' and '_type' fields (with both being truthy),
 *   indicating that no additional fields exist.
 * - At least one field in the template has a truthy 'tool_mode' property.
 *
 * @param template - The API template to evaluate.
 * @returns True if the template supports tool mode capability; otherwise, false.
 */
export function checkHasToolMode(template: APITemplateType): boolean {
  if (!template) return false;

  const templateKeys = Object.keys(template);

  // Check if the template has no additional fields
  const hasNoAdditionalFields =
    templateKeys.length === 2 &&
    Boolean(template.code) &&
    Boolean(template._type);

  // Check if the template has at least one field with a truthy 'tool_mode' property
  const hasToolModeFields = Object.values(template).some((field) =>
    Boolean(field.tool_mode),
  );
  // Check if the component is already in tool mode
  // This occurs when the template has exactly 3 fields: _type, code, and tools_metadata
  const isInToolMode =
    templateKeys.length === 3 &&
    Boolean(template.code) &&
    Boolean(template._type) &&
    Boolean(template.tools_metadata);

  return hasNoAdditionalFields || hasToolModeFields || isInToolMode;
}

export function buildPositionDictionary(nodes: AllNodeType[]) {
  const positionDictionary = {};
  nodes.forEach((node) => {
    positionDictionary[node.position.x] = node.position.y;
  });
  return positionDictionary;
}

export function hasStreaming(nodes: AllNodeType[]) {
  return nodes.some((node) => node.data.node?.template?.stream?.value);
}
