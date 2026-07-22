import type { UseMutationResult } from "@tanstack/react-query";
import { cloneDeep, debounce } from "lodash";
import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import type { APIClassType, ResponseErrorDetailAPI } from "@/types/api";
import i18n from "../../i18n";
import { updateHiddenOutputs } from "./update-hidden-outputs";

// Map to store debounced functions for each node ID + parameter combination
const debouncedFunctions = new Map<string, ReturnType<typeof debounce>>();

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
            if (newTemplate) {
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

  // Enabling Tool Mode mounts the tools_metadata field, which queues its own
  // debounced refresh. If the user turns Tool Mode off before that refresh
  // runs, the queued request still carries tool_mode=true and can restore the
  // Toolset output after the off response. The explicit toggle supersedes that
  // pending metadata refresh.
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

  // Tool Mode is a discrete toggle, so delaying it like a text input leaves
  // the node in its previous output shape and gives slower refresh responses
  // a chance to repaint the toggle with stale state.
  if (parameterName === "tool_mode") {
    await debouncedFunction?.flush();
  }
};
