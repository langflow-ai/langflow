import type { UseMutationResult } from "@tanstack/react-query";
import { cloneDeep, debounce } from "lodash";
import {
  ERROR_UPDATING_COMPONENT,
  SAVE_DEBOUNCE_TIME,
  TITLE_ERROR_UPDATING_COMPONENT,
} from "@/constants/constants";
import type { APIClassType, ResponseErrorDetailAPI } from "@/types/api";
import {
  extractOAuthError,
  handleMCPOAuthFlow,
} from "@/controllers/API/queries/mcp/use-mcp-oauth";
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
  isRefresh?: boolean,
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

            // Check if this is an OAuth required error
            const oauthError = extractOAuthError(error);
            if (oauthError) {
              // Show notice that OAuth is required
              setErrorData({
                title: "OAuth Authentication Required",
                list: [
                  `The MCP server requires authentication. Starting OAuth flow...`,
                ],
              });

              // Handle the OAuth flow - pass full error object with credentials
              const result = await handleMCPOAuthFlow(oauthError);

              if (result.success) {
                // OAuth succeeded - retry the mutation
                setErrorData({
                  title: "Authentication Successful",
                  list: [
                    "OAuth authentication completed. Please try your action again.",
                  ],
                });
              } else {
                // OAuth failed
                setErrorData({
                  title: "OAuth Authentication Failed",
                  list: [result.error || "Failed to authenticate with MCP server"],
                });
              }
              return;
            }

            // Regular error handling
            setErrorData({
              title: TITLE_ERROR_UPDATING_COMPONENT,
              list: [
                typeof error.response?.data?.detail === "string"
                  ? error.response.data.detail
                  : ERROR_UPDATING_COMPONENT,
              ],
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
    isRefresh,
  );
};
