/**
 * Utility functions for handling payload generation and tweaks logic
 * across different API code generators (Python, JavaScript, cURL)
 */

import useFlowStore from "@/stores/flowStore";

// ========== Types and Interfaces ==========

interface PayloadArgs {
  input_value: string;
  input_type: string;
  output_type: string;
  includeSessionId: boolean;
}

interface NodeInfo {
  id: string;
  data?: {
    type: string;
  };
}

interface InputOutputInfo {
  filteredNodes: Record<string, NodeInfo>;
  chatInputNode: NodeInfo | null;
  chatOutputNode: NodeInfo | null;
  hasChatInput: boolean;
  hasChatOutput: boolean;
}

type SupportedLanguageFormat = "python" | "javascript" | "json";

// ========== Constants ==========

const DEFAULT_SESSION_ID = "user_1";
const DEFAULT_INDENT = 2;

/**
 * Configuration for which fields to exclude from base payload for each component type
 */
const COMPONENT_FIELD_FILTERS: Record<string, string[]> = {
  ChatInput: ["input_value"],
  ChatOutput: ["output_type"],
  // Add more component types and their filtered fields as needed
} as const;

/**
 * Configuration for base payload fields and their value generators
 */
const BASE_PAYLOAD_FIELDS: Record<
  string,
  (args: PayloadArgs) => string | null
> = {
  input_value: (args) => args.input_value,
  output_type: (args) => args.output_type,
  input_type: (args) => args.input_type,
  session_id: (args) => (args.includeSessionId ? DEFAULT_SESSION_ID : null),
} as const;

/**
 * Language-specific formatting rules
 */
const LANGUAGE_FORMATTERS: Record<
  SupportedLanguageFormat,
  (value: string) => string
> = {
  python: (value) =>
    value
      .replace(/true/g, "True")
      .replace(/false/g, "False")
      .replace(/null/g, "None"),
  javascript: (value) => value,
  json: (value) => value,
} as const;

// ========== Helper Functions ==========

/**
 * Safely gets the flow store state
 */
function getFlowStoreState() {
  try {
    return useFlowStore.getState();
  } catch (error) {
    console.error("Failed to get flow store state:", error);
    return { nodes: [], inputs: [], outputs: [] };
  }
}

/**
 * Finds nodes by component type in inputs or outputs
 */
function findNodeByComponentType(
  componentType: string,
  nodes: NodeInfo[],
  inputs: any[],
  outputs: any[],
): NodeInfo | null {
  // Look in inputs first
  const inputNode = nodes.find((node) =>
    inputs.some(
      (input) => input.id === node.id && input.type === componentType,
    ),
  );

  if (inputNode) return inputNode;

  // If not found in inputs, look in outputs
  const outputNode = nodes.find((node) =>
    outputs.some(
      (output) => output.id === node.id && output.type === componentType,
    ),
  );

  return outputNode || null;
}

/**
 * Validates tweaks object structure
 */
function isValidTweaksObject(tweaksObject: any): boolean {
  return (
    tweaksObject &&
    typeof tweaksObject === "object" &&
    !Array.isArray(tweaksObject)
  );
}

/**
 * Validates node parameters structure
 */
function isValidNodeParams(nodeParams: any): boolean {
  return (
    nodeParams && typeof nodeParams === "object" && !Array.isArray(nodeParams)
  );
}

// ========== Main Functions ==========

/**
 * Gets information about nodes that have configured field filters
 */
export function getInputOutputInfo(): InputOutputInfo {
  const { nodes, inputs, outputs } = getFlowStoreState();

  if (!nodes.length) {
    return {
      filteredNodes: {},
      chatInputNode: null,
      chatOutputNode: null,
      hasChatInput: false,
      hasChatOutput: false,
    };
  }

  const filteredComponentTypes = Object.keys(COMPONENT_FIELD_FILTERS);
  const filteredNodes: Record<string, NodeInfo> = {};

  // Find nodes for each configured component type
  filteredComponentTypes.forEach((componentType) => {
    const foundNode = findNodeByComponentType(
      componentType,
      nodes,
      inputs,
      outputs,
    );
    if (foundNode) {
      filteredNodes[componentType] = foundNode;
    }
  });

  return {
    filteredNodes,
    // Legacy properties for backward compatibility
    chatInputNode: filteredNodes.ChatInput || null,
    chatOutputNode: filteredNodes.ChatOutput || null,
    hasChatInput: !!filteredNodes.ChatInput,
    hasChatOutput: !!filteredNodes.ChatOutput,
  };
}

/**
 * Gets the set of fields that should be excluded from base payload
 * based on what's present in tweaks and component type filters
 */
export function getExcludedBasePayloadKeys(
  tweaksObject: any,
  activeTweaks: boolean,
): Set<string> {
  const excludedFields = new Set<string>();

  if (!isValidTweaksObject(tweaksObject) || !activeTweaks) {
    return excludedFields;
  }

  const { nodes } = getFlowStoreState();

  // Process each component in tweaks
  Object.entries(tweaksObject).forEach(([nodeId, nodeParams]) => {
    if (!isValidNodeParams(nodeParams)) return;

    const paramKeys = Object.keys(nodeParams as Record<string, any>);
    const currentNode = nodes.find((node) => node.id === nodeId);

    if (!currentNode?.data?.type) return;

    const nodeType = currentNode.data.type;
    const fieldsToFilter = COMPONENT_FIELD_FILTERS[nodeType];

    if (fieldsToFilter) {
      // Add fields that are both filtered and present in tweaks
      fieldsToFilter.forEach((field) => {
        if (paramKeys.includes(field)) {
          excludedFields.add(field);
        }
      });
    }
  });

  return excludedFields;
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
  const excludedFields = getExcludedBasePayloadKeys(tweaksObject, activeTweaks);

  const args: PayloadArgs = {
    input_value,
    input_type,
    output_type,
    includeSessionId,
  };

  // Build payload from configured fields
  Object.entries(BASE_PAYLOAD_FIELDS).forEach(([field, valueGetter]) => {
    // Skip if field is excluded by filtering logic
    if (excludedFields.has(field)) return;

    try {
      const value = valueGetter(args);
      // Only add field if value is not null/undefined
      if (value != null) {
        basePayload[field] = value;
      }
    } catch (error) {
      console.error(`Error generating value for field ${field}:`, error);
    }
  });

  return basePayload;
}

/**
 * Applies proper indentation to closing braces
 */
function formatIndentation(jsonString: string, indent: number): string {
  const indentSpaces = " ".repeat(Math.max(0, indent / 2));
  return jsonString.replace(/\n}/g, `\n${indentSpaces}}`);
}

/**
 * Gets formatted tweaks string for different languages
 */
export function getFormattedTweaksString(
  tweaksObject: any,
  activeTweaks: boolean,
  format: SupportedLanguageFormat = "json",
  indent = DEFAULT_INDENT,
): string {
  if (!isValidTweaksObject(tweaksObject) || !activeTweaks) {
    return "{}";
  }

  try {
    // Generate base JSON string
    let tweaksString = JSON.stringify(tweaksObject, null, Math.max(0, indent));

    // Apply language-specific formatting
    const formatter = LANGUAGE_FORMATTERS[format];
    if (formatter) {
      tweaksString = formatter(tweaksString);
    }

    // Apply proper indentation
    return formatIndentation(tweaksString, indent);
  } catch (error) {
    console.error("Error formatting tweaks string:", error);
    return "{}";
  }
}

// ========== Legacy Functions ==========

/**
 * @deprecated Use getExcludedBasePayloadKeys instead
 * Collects all keys from tweaks object to avoid duplicates in base payload
 *
 * This function is maintained for backward compatibility but should not be used
 * in new code. Use getExcludedBasePayloadKeys for more precise filtering.
 */
export function collectTweaksKeys(
  tweaksObject: any,
  activeTweaks: boolean,
): Set<string> {
  console.warn(
    "collectTweaksKeys is deprecated. Use getExcludedBasePayloadKeys instead.",
  );

  const tweaksKeys = new Set<string>();

  if (!isValidTweaksObject(tweaksObject) || !activeTweaks) {
    return tweaksKeys;
  }

  try {
    Object.values(tweaksObject).forEach((component: any) => {
      if (isValidNodeParams(component)) {
        Object.keys(component).forEach((key) => tweaksKeys.add(key));
      }
    });
  } catch (error) {
    console.error("Error collecting tweaks keys:", error);
  }

  return tweaksKeys;
}
