import { cloneDeep } from "lodash";
import { useCallback } from "react";
import { markNextSaveCause } from "@/stores/flowSaveCauseStore";
import type { AllNodeType, FlowType, GenericNodeType } from "@/types/flow";
import { copySavedFieldValues, walkFlowNodes } from "@/utils/grouped-nodes";
import {
  cleanEdges,
  generateNodeOutputs,
  generateNodeTemplate,
  processFlowEdges,
  scapeJSONParse,
} from "@/utils/reactflowUtils";
import type { APIClassType } from "../../types/api";
import { updateHiddenOutputs } from "../helpers/update-hidden-outputs";

export type UpdateNodesType = {
  nodeId: string;
  newNode: APIClassType;
  code: string;
  name: string;
  type?: string;
};

function normalizeGroupEdges(flow: FlowType): void {
  if (!flow.data) return;
  const data = flow.data;
  data.edges = (data.edges ?? []).map((edge) => {
    // Normalize each edge separately. A saved group may mix legacy, escaped,
    // and structured handles. The importer otherwise detects one format per flow.
    const singleEdgeFlow = { ...flow, data: { ...data, edges: [edge] } };
    processFlowEdges(singleEdgeFlow);
    const normalized = singleEdgeFlow.data.edges[0];
    normalized.data = {
      ...normalized.data,
      sourceHandle: scapeJSONParse(normalized.sourceHandle!),
      targetHandle: scapeJSONParse(normalized.targetHandle!),
    };
    return normalized;
  });
}

const useUpdateAllNodes = (
  setNodes: (
    update: AllNodeType[] | ((oldState: AllNodeType[]) => AllNodeType[]),
  ) => void,
  updateNodeInternals: (nodeId: string) => void,
) => {
  const updateAllNodes = useCallback(
    (updates: UpdateNodesType[]) => {
      // Everything these updates write is one change: the component updates.
      markNextSaveCause("upgrade_component");
      setNodes((oldNodes) => {
        const newNodes = cloneDeep(oldNodes);
        const contexts = new Map(
          Array.from(walkFlowNodes(newNodes), (context) => [
            context.node.id,
            context,
          ]),
        );
        const changedChildren = new Map<GenericNodeType, Set<string>>();
        const changedGroupFields = new Map<string, Set<string>>();
        const visibleNodeIds = new Set<string>();

        const groupsToUpdate = new Set(
          updates.flatMap(
            ({ nodeId }) => contexts.get(nodeId)?.ancestors ?? [],
          ),
        );
        for (const group of groupsToUpdate) {
          // Use the saved contracts before replacement, including fields removed
          // by this update, so edge cleanup can compare the old and new handles.
          if (group.data.node?.flow) normalizeGroupEdges(group.data.node.flow);
        }

        updates.forEach(({ nodeId, newNode, code, name, type }) => {
          const context = contexts.get(nodeId);
          if (!context || context.node.type !== "genericNode") return;

          const updatedNode = context.node;
          const outputs = updatedNode?.data.node?.outputs;

          updatedNode.data = {
            ...updatedNode.data,
            node: {
              ...cloneDeep(newNode),
              description:
                newNode.description ?? updatedNode.data.node?.description,
              display_name:
                newNode.display_name ?? updatedNode.data.node?.display_name,
              edited: false,
            },
          };

          if (type) {
            updatedNode.data.type = type;
          }

          updatedNode.data.node!.template[name].value = code;

          const updatedOutputs = updatedNode.data.node?.outputs;
          updatedNode.data.node!.outputs = updateHiddenOutputs(
            outputs!,
            updatedOutputs!,
          );

          visibleNodeIds.add(context.ancestors[0]?.id ?? nodeId);
          let childId = nodeId;
          for (const ancestor of [...context.ancestors].reverse()) {
            const children = changedChildren.get(ancestor) ?? new Set<string>();
            children.add(childId);
            changedChildren.set(ancestor, children);
            childId = ancestor.id;
          }
        });

        // Rebuild inner groups before their parents so exposed contracts match
        // the updated child. Unchanged siblings retain values edited on the group.
        for (const { node } of [...contexts.values()].reverse()) {
          if (node.type !== "genericNode") continue;
          const children = changedChildren.get(node);
          const groupNode = node.data.node;
          const flow = groupNode?.flow;
          if (!children || !groupNode || !flow?.data) continue;
          flow.data.edges = cleanEdges(
            flow.data.nodes,
            flow.data.edges ?? [],
          ).edges;
          const template = generateNodeTemplate(flow);
          const changedFields = new Set<string>();
          groupNode.template = Object.fromEntries(
            Object.entries(template).map(([name, field]) => {
              const previous =
                field?.proxy &&
                Object.entries(groupNode.template).find(
                  ([, old]) =>
                    old?.proxy?.id === field.proxy!.id &&
                    old.proxy.field === field.proxy!.field,
                );
              const proxy = field?.proxy;
              const childGroupFields =
                proxy && changedGroupFields.get(proxy.id);
              const changed =
                proxy &&
                children.has(proxy.id) &&
                (!childGroupFields || childGroupFields.has(proxy.field));
              if (previous && !changed) {
                copySavedFieldValues(previous[1], field);
              }
              // Saved groups may use a different exposed name for the same proxy.
              const exposedName = previous ? previous[0] : name;
              if (changed) changedFields.add(exposedName);
              return [exposedName, field];
            }),
          );
          changedGroupFields.set(node.id, changedFields);
          const outputs = generateNodeOutputs(flow).map((output) => {
            const previous = groupNode.outputs?.find(
              (old) =>
                old.proxy?.id === output.proxy?.id &&
                old.proxy?.name === output.proxy?.name,
            );
            return previous ? { ...output, name: previous.name } : output;
          });
          groupNode.outputs = updateHiddenOutputs(
            groupNode.outputs ?? [],
            outputs,
          );
        }
        visibleNodeIds.forEach((id) => updateNodeInternals(id));
        return newNodes;
      });
    },
    [setNodes, updateNodeInternals],
  );

  return updateAllNodes;
};

export default useUpdateAllNodes;
