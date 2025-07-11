import {
  ERROR_UPDATING_COMPONENT,
  SAVE_DEBOUNCE_TIME,
  TITLE_ERROR_UPDATING_COMPONENT,
} from "@/constants/constants";
import { APIClassType, ResponseErrorDetailAPI } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { cloneDeep, debounce } from "lodash";
import { updateHiddenOutputs } from "./update-hidden-outputs";

// Map to store debounced functions for each node ID
const debouncedFunctions = new Map<string, ReturnType<typeof debounce>>();

export const mutateTemplate = async (
  newValue,
  nodeId: string,
  node: APIClassType,
  setNodeClass,
  postTemplateValue: UseMutationResult<
    APIClassType | undefined,
    ResponseErrorDetailAPI,
    any
  >,
  setErrorData,
  parameterName?: string,
  callback?: () => void,
  toolMode?: boolean,
) => {
  // Get or create a debounced function for this node ID
  if (!debouncedFunctions.has(nodeId)) {
    debouncedFunctions.set(
      nodeId,
      debounce(
        async (
          newValue,
          node: APIClassType,
          setNodeClass,
          postTemplateValue: UseMutationResult<
            APIClassType | undefined,
            ResponseErrorDetailAPI,
            any
          >,
          setErrorData,
          parameterName?: string,
          callback?: () => void,
          toolMode?: boolean,
        ) => {
          try {
            const newNode = cloneDeep(node);
            const newTemplate = await postTemplateValue.mutateAsync({
              value: newValue,
              field_name: parameterName,
              tool_mode: toolMode ?? node.tool_mode,
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
                  console.log("Node not found");
                } else {
                  throw e;
                }
              }
            }
            callback?.();
          } catch (e) {
            const error = e as ResponseErrorDetailAPI;
            setErrorData({
              title: TITLE_ERROR_UPDATING_COMPONENT,
              list: [error.response?.data?.detail || ERROR_UPDATING_COMPONENT],
            });
          }
        },
        SAVE_DEBOUNCE_TIME,
      ),
    );
  }

  // Call the debounced function for this specific node
  debouncedFunctions.get(nodeId)?.(
    newValue,
    node,
    setNodeClass,
    postTemplateValue,
    setErrorData,
    parameterName,
    callback,
    toolMode,
  );
};
