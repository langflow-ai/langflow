import type { UseMutationResult } from "@tanstack/react-query";
import { cloneDeep, debounce } from "lodash";
import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import {
  applyNodeFieldUpdates,
  buildThreeWayComponentNodeUpdates,
  type ThreeWayComponentDiffPolicy,
} from "@/hooks/flows/flow-operation-diff";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType, ResponseErrorDetailAPI } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import type { NodeFieldPath } from "@/types/flow-operations";
import i18n from "../../i18n";
import { updateHiddenOutputs } from "./update-hidden-outputs";

// Map to store debounced functions for each node ID + parameter combination
const debouncedFunctions = new Map<string, ReturnType<typeof debounce>>();

type PostTemplateValueVariables = {
  value: unknown;
  field_name?: string;
  tool_mode?: boolean;
  is_refresh?: boolean;
};

type PostTemplateValueMutation = UseMutationResult<
  APIClassType | undefined,
  ResponseErrorDetailAPI,
  PostTemplateValueVariables
>;

function pathStartsWith(path: NodeFieldPath, prefix: string[]): boolean {
  return prefix.every((segment, index) => path[index] === segment);
}

function buildRefreshPolicy(
  parameterName?: string,
  toolMode?: boolean,
  isRefresh?: boolean,
): ThreeWayComponentDiffPolicy {
  return {
    generatedWinsOnOverlap: (path) => {
      if (parameterName === "tool_mode" && toolMode !== undefined) {
        return (
          pathStartsWith(path, ["data", "node", "tool_mode"]) ||
          pathStartsWith(path, ["data", "node", "outputs"])
        );
      }
      if (
        parameterName &&
        (isRefresh ||
          parameterName.includes("auth") ||
          parameterName.includes("connection"))
      ) {
        return pathStartsWith(path, [
          "data",
          "node",
          "template",
          parameterName,
        ]);
      }
      return false;
    },
  };
}

export const mutateTemplate = async (
  newValue,
  nodeId: string,
  node: APIClassType,
  setNodeClass,
  postTemplateValue: PostTemplateValueMutation,
  setErrorData,
  parameterName?: string,
  callback?: () => void,
  toolMode?: boolean,
  isRefresh?: boolean,
) => {
  // Different parameters must debounce independently to avoid one field's
  // refresh cancelling another's during concurrent mount calls.
  const debounceKey = parameterName ? `${nodeId}-${parameterName}` : nodeId;
  if (!debouncedFunctions.has(debounceKey)) {
    debouncedFunctions.set(
      debounceKey,
      debounce(
        async (
          newValue,
          node: APIClassType,
          setNodeClass,
          postTemplateValue: PostTemplateValueMutation,
          setErrorData,
          parameterName?: string,
          callback?: () => void,
          toolMode?: boolean,
          isRefresh?: boolean,
        ) => {
          try {
            const newNode = cloneDeep(node);
            const newTemplate = await postTemplateValue.mutateAsync({
              value: newValue,
              field_name: parameterName,
              tool_mode: toolMode ?? node.tool_mode,
              is_refresh: isRefresh ?? false,
            });
            if (newTemplate) {
              newNode.template = newTemplate.template;
              newNode.outputs = newTemplate.outputs;
              newNode.tool_mode = toolMode ?? node.tool_mode;
              newNode.last_updated = newTemplate.last_updated;
              const localGraphNode = useFlowStore.getState().getNode(nodeId);
              const localNode =
                (localGraphNode?.data?.node as APIClassType | undefined) ??
                node;
              const collaborationUpdates = buildThreeWayComponentNodeUpdates(
                nodeId,
                node as unknown as Record<string, unknown>,
                localNode as unknown as Record<string, unknown>,
                newNode as unknown as Record<string, unknown>,
                buildRefreshPolicy(parameterName, toolMode, isRefresh),
              );
              try {
                if (localGraphNode) {
                  const mergedGraphNode = applyNodeFieldUpdates(
                    localGraphNode as unknown as Record<string, unknown>,
                    collaborationUpdates,
                  ) as unknown as AllNodeType;
                  useFlowStore
                    .getState()
                    .setNode(
                      nodeId,
                      mergedGraphNode as typeof localGraphNode,
                      true,
                      undefined,
                      collaborationUpdates.length > 0
                        ? { collaborationUpdates }
                        : undefined,
                    );
                  setNodeClass(mergedGraphNode.data.node);
                } else {
                  newNode.outputs = updateHiddenOutputs(
                    node.outputs ?? [],
                    newTemplate.outputs ?? [],
                  );
                  setNodeClass(newNode);
                }
              } catch (e) {
                if (e instanceof Error && e.message === "Node not found") {
                  console.error("Node not found");
                } else {
                  throw e;
                }
              }
            }
            callback?.();
          } catch (e) {
            const error = e as ResponseErrorDetailAPI;
            setErrorData({
              title: i18n.t("input.titleErrorUpdatingComponent"),
              list: [
                error.response?.data?.detail ||
                  i18n.t("input.errorUpdatingComponent"),
              ],
            });
          }
        },
        SAVE_DEBOUNCE_TIME,
      ),
    );
  }

  debouncedFunctions.get(debounceKey)?.(
    newValue,
    node,
    setNodeClass,
    postTemplateValue,
    setErrorData,
    parameterName,
    callback,
    toolMode,
    isRefresh,
  );
};
