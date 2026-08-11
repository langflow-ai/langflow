import type { UseMutationResult } from "@tanstack/react-query";
import { cloneDeep, debounce } from "lodash";
import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType, ResponseErrorDetailAPI } from "@/types/api";
import i18n from "../../i18n";
import { updateHiddenOutputs } from "./update-hidden-outputs";

const debouncedFunctions = new Map<string, ReturnType<typeof debounce>>();

const getNodeCode = (nodeId: string): unknown => {
  const currentNode = useFlowStore
    .getState()
    .nodes.find((flowNode) => flowNode.id === nodeId);
  return currentNode?.data?.node?.template?.code?.value;
};

// A refresh answers for the code that was current when it left, and applying it
// replaces the whole template — a code save landing meanwhile would be reverted.
const isStaleForNode = (
  nodeId: string,
  requestedNode: APIClassType,
): boolean => {
  const requestedCode = requestedNode.template?.code?.value;
  if (requestedCode === undefined) return false;
  const currentCode = getNodeCode(nodeId);
  if (currentCode === undefined) return false;
  return currentCode !== requestedCode;
};

export const mutateTemplate = async (
  newValue,
  nodeId: string,
  node: APIClassType,
  setNodeClass,
  postTemplateValue: UseMutationResult<
    APIClassType | undefined,
    ResponseErrorDetailAPI,
    // biome-ignore lint/suspicious/noExplicitAny: legacy mutation payload
    any
  >,
  setErrorData,
  parameterName?: string,
  callback?: () => void,
  toolMode?: boolean,
  isRefresh?: boolean,
) => {
  // Per-parameter keys keep one field's refresh from cancelling another's on mount.
  const debounceKey = parameterName ? `${nodeId}-${parameterName}` : nodeId;
  if (!debouncedFunctions.has(debounceKey)) {
    debouncedFunctions.set(
      debounceKey,
      debounce(
        async (
          newValue,
          node: APIClassType,
          setNodeClass,
          postTemplateValue: UseMutationResult<
            APIClassType | undefined,
            ResponseErrorDetailAPI,
            // biome-ignore lint/suspicious/noExplicitAny: legacy mutation payload
            any
          >,
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
            if (newTemplate && !isStaleForNode(nodeId, node)) {
              newNode.template = newTemplate.template;
              newNode.outputs = updateHiddenOutputs(
                newNode.outputs ?? [],
                newTemplate.outputs ?? [],
              );
              newNode.tool_mode = toolMode ?? node.tool_mode;
              newNode.last_updated = newTemplate.last_updated;
              try {
                setNodeClass(newNode);
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
            // LE-2045: the fallback below identifies nothing, so a client-side
            // throw is otherwise indistinguishable from a failed request.
            console.error(
              `Failed to update template for node ${nodeId}, field ${parameterName}`,
              e,
            );
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

  // A queued tools_metadata refresh still carries tool_mode=true and would restore
  // the Toolset output after an off response, so the explicit toggle supersedes it.
  if (parameterName === "tool_mode") {
    debouncedFunctions.get(`${nodeId}-tools_metadata`)?.cancel();
  }

  const debouncedFunction = debouncedFunctions.get(debounceKey);
  debouncedFunction?.(
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

  // Debouncing a discrete toggle like a text input lets slower refresh responses
  // repaint it with stale state, so Tool Mode is flushed immediately.
  if (parameterName === "tool_mode") {
    await debouncedFunction?.flush();
  }
};
