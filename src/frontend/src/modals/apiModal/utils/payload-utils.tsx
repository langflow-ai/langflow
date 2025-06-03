/**
 * Utility functions for handling payload generation and tweaks logic
 * across different API code generators (Python, JavaScript, cURL)
 */

import { INPUT_TYPES, OUTPUT_TYPES } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";

/**
 * Gets information about input and output nodes from the current flow
 */
export function getInputOutputInfo() {
  const nodes = useFlowStore.getState().nodes;
  const inputs = useFlowStore.getState().inputs;
  const outputs = useFlowStore.getState().outputs;

  // Find ChatInput and ChatOutput nodes specifically
  const chatInputNode = nodes.find((node) =>
    inputs.some((input) => input.id === node.id && input.type === "ChatInput"),
  );
  const chatOutputNode = nodes.find((node) =>
    outputs.some(
      (output) => output.id === node.id && output.type === "ChatOutput",
    ),
  );

  return {
    chatInputNode,
    chatOutputNode,
    hasChatInput: !!chatInputNode,
    hasChatOutput: !!chatOutputNode,
  };
}

/**
 * Collects keys that should be excluded from base payload, considering node types
 * Only excludes base payload items when they come from appropriate component types
 */
export function getExcludedBasePayloadKeys(
  tweaksObject: any,
  activeTweaks: boolean,
): {
  excludeInputValue: boolean;
  excludeInputType: boolean;
  excludeOutputType: boolean;
  excludeSessionId: boolean;
} {
  const result = {
    excludeInputValue: false,
    excludeInputType: false,
    excludeOutputType: false,
    excludeSessionId: false,
  };

  if (!tweaksObject || !activeTweaks) {
    return result;
  }

  const { chatInputNode, chatOutputNode } = getInputOutputInfo();

  // Check each component in tweaks
  Object.entries(tweaksObject).forEach(
    ([nodeId, nodeParams]: [string, any]) => {
      if (!nodeParams || typeof nodeParams !== "object") return;

      const paramKeys = Object.keys(nodeParams);

      // Only exclude input_value if it comes from a ChatInput node
      if (
        chatInputNode &&
        nodeId === chatInputNode.id &&
        paramKeys.includes("input_value")
      ) {
        result.excludeInputValue = true;
      }

      // Only exclude input_type if it comes from a ChatInput node
      if (
        chatInputNode &&
        nodeId === chatInputNode.id &&
        paramKeys.includes("input_type")
      ) {
        result.excludeInputType = true;
      }

      // Only exclude output_type if it comes from a ChatOutput node
      if (
        chatOutputNode &&
        nodeId === chatOutputNode.id &&
        paramKeys.includes("output_type")
      ) {
        result.excludeOutputType = true;
      }

      // Exclude session_id if it comes from any input/output component
      const nodes = useFlowStore.getState().nodes;
      const currentNode = nodes.find((node) => node.id === nodeId);
      if (currentNode && paramKeys.includes("session_id")) {
        const nodeType = currentNode.data?.type;
        if (INPUT_TYPES.has(nodeType) || OUTPUT_TYPES.has(nodeType)) {
          result.excludeSessionId = true;
        }
      }
    },
  );

  return result;
}

/**
 * Builds base payload excluding keys that exist in tweaks from appropriate component types
 */
export function buildBasePayload(
  tweaksObject: any,
  activeTweaks: boolean,
  input_value: string,
  input_type: string,
  output_type: string,
  includeSessionId = false,
): Record<string, string> {
  const basePayload: Record<string, string> = {};

  const excludedKeys = getExcludedBasePayloadKeys(tweaksObject, activeTweaks);

  if (!excludedKeys.excludeInputValue) {
    basePayload.input_value = input_value;
  }
  if (!excludedKeys.excludeOutputType) {
    basePayload.output_type = output_type;
  }
  if (!excludedKeys.excludeInputType) {
    basePayload.input_type = input_type;
  }

  // Add session_id for JavaScript if not in tweaks and if requested
  if (includeSessionId && !excludedKeys.excludeSessionId) {
    basePayload.session_id = "user_1";
  }

  return basePayload;
}

/**
 * Gets formatted tweaks string for different languages
 */
export function getFormattedTweaksString(
  tweaksObject: any,
  activeTweaks: boolean,
  format: "python" | "javascript" | "json" = "json",
  indent = 2,
): string {
  if (!tweaksObject || !activeTweaks) {
    return "{}";
  }

  let tweaksString = JSON.stringify(tweaksObject, null, indent);

  if (format === "python") {
    tweaksString = tweaksString
      .replace(/true/g, "True")
      .replace(/false/g, "False")
      .replace(/null/g, "None");
  }

  // Add proper indentation to the closing brace
  const indentSpaces = " ".repeat(indent / 2);
  tweaksString = tweaksString.replace(/\n}/g, `\n${indentSpaces}}`);

  return tweaksString;
}

// Legacy function for backward compatibility - now deprecated
/**
 * @deprecated Use getExcludedBasePayloadKeys instead
 * Collects all keys from tweaks object to avoid duplicates in base payload
 */
export function collectTweaksKeys(
  tweaksObject: any,
  activeTweaks: boolean,
): Set<string> {
  const tweaksKeys = new Set<string>();
  if (tweaksObject && activeTweaks) {
    Object.values(tweaksObject).forEach((component: any) => {
      if (component && typeof component === "object") {
        Object.keys(component).forEach((key) => tweaksKeys.add(key));
      }
    });
  }
  return tweaksKeys;
}
