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

interface PayloadEntry {
  key: string;
  value: string;
  comment: string;
}

// ========== Constants ==========

const DEFAULT_SESSION_ID = "user_1";
const DEFAULT_INDENT = 2;

/**
 * Configuration for which fields to exclude from base payload for each component type
 * @deprecated This is now handled by the caller (code-tabs.tsx) which passes excludedFields
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

/**
 * Comment configurations for different languages
 */
const COMMENT_CONFIGS = {
  python: {
    prefix: "  # ",
    inputValue: "The input value to be processed by the flow",
    outputType: "Specifies the expected output format",
    inputType: "Specifies the input format",
    sessionId: "Optional: Use session tracking if needed",
    tweaks: " # Custom tweaks to modify flow behavior",
  },
  javascript: {
    prefix: " // ",
    inputValue: "The input value to be processed by the flow",
    outputType: "Specifies the expected output format",
    inputType: "Specifies the input format",
    sessionId: "Optional: Use session tracking if needed",
    tweaks: "",
  },
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

// ========== Payload Generation Utilities ==========

/**
 * Generates payload entries with appropriate comments for the specified language
 */
export function generatePayloadEntries(
  basePayload: Record<string, string>,
  language: "python" | "javascript",
): PayloadEntry[] {
  const config = COMMENT_CONFIGS[language];

  return Object.entries(basePayload).map(([key, value]) => {
    let comment = "";

    if (key === "input_value") {
      comment = config.prefix + config.inputValue;
    } else if (key === "output_type") {
      comment = config.prefix + config.outputType;
    } else if (key === "input_type") {
      comment = config.prefix + config.inputType;
    } else if (key === "session_id") {
      comment = config.prefix + config.sessionId;
    }

    return { key, value, comment };
  });
}

/**
 * Builds payload string with proper formatting and comma placement
 */
export function buildPayloadString(
  payloadEntries: PayloadEntry[],
  hasTweaks: boolean,
  language: "python" | "javascript",
): string {
  if (payloadEntries.length === 0) return "";

  const formattedEntries = payloadEntries.map((entry, index) => {
    const isLastEntry = index === payloadEntries.length - 1;
    const needsComma = hasTweaks || !isLastEntry;

    const entryString = `    "${entry.key}": "${entry.value}"${entry.comment}`;

    if (language === "python" && needsComma && entry.comment) {
      // For Python, insert comma before comment
      const commentIndex = entryString.indexOf("  #");
      if (commentIndex !== -1) {
        return (
          entryString.slice(0, commentIndex) +
          "," +
          entryString.slice(commentIndex)
        );
      } else {
        return entryString + ",";
      }
    } else if (language === "javascript" && needsComma) {
      // For JavaScript, just add comma at the end
      return entryString + ",";
    }

    return entryString;
  });

  return formattedEntries.join("\n");
}

/**
 * Generates the tweaks line for the payload
 */
export function generateTweaksLine(
  hasTweaks: boolean,
  hasPayloadEntries: boolean,
  tweaksString: string,
  language: "python" | "javascript",
): string {
  if (!hasTweaks) return "";

  const config = COMMENT_CONFIGS[language];
  const prefix = hasPayloadEntries ? "\n" : "";

  if (language === "python") {
    return `${prefix}    "tweaks": ${tweaksString}${config.tweaks}`;
  } else {
    return `${hasPayloadEntries ? ",\n" : ""}    "tweaks": ${tweaksString}`;
  }
}

// ========== Main Functions ==========

/**
 * Gets information about nodes that have configured field filters
 * @deprecated This function is kept for backward compatibility but should be replaced by caller logic
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
 * @deprecated This function is now replaced by caller-provided excludedFields
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
 * Builds base payload excluding keys that are provided in excludedFields set
 */
export function buildBasePayload(
  tweaksObject: any,
  activeTweaks: boolean,
  input_value: string,
  input_type: string,
  output_type: string,
  includeSessionId = false,
  excludedFields?: Set<string>,
): Record<string, string> {
  const basePayload: Record<string, string> = {};

  // Use provided excludedFields or fall back to legacy logic for backward compatibility
  const fieldsToExclude =
    excludedFields || getExcludedBasePayloadKeys(tweaksObject, activeTweaks);

  const args: PayloadArgs = {
    input_value,
    input_type,
    output_type,
    includeSessionId,
  };

  // Build payload from configured fields
  Object.entries(BASE_PAYLOAD_FIELDS).forEach(([field, valueGetter]) => {
    // Skip if field is excluded by filtering logic
    if (fieldsToExclude.has(field)) return;

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
