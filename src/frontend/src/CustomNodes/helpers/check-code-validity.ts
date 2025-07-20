import { componentsToIgnoreUpdate } from "@/constants/constants";
import type { OutputFieldType } from "@/types/api";
import type { NodeDataType } from "../../types/flow";

// Returns true if the code is outdated (code string changed and not ignored)
const codeIsOutdated = (
  currentCode: string,
  thisNodesCode: string,
  type: string,
): boolean => {
  return !!(
    currentCode &&
    thisNodesCode &&
    currentCode !== thisNodesCode &&
    !componentsToIgnoreUpdate.includes(type)
  );
};

// Returns true if there is a breaking change (outputs, template keys, or input_types)
const codeHasBreakingChange = (
  originalOutputs?: OutputFieldType[],
  userOutputs?: OutputFieldType[],
  originalTemplate?: { [key: string]: any },
  userTemplate?: { [key: string]: any },
): boolean => {
  // Check outputs
  if (
    originalOutputs &&
    userOutputs &&
    !outputsAreEqual(originalOutputs, userOutputs)
  ) {
    return true;
  }
  // Check template keys
  if (
    originalTemplate &&
    userTemplate &&
    !templateKeysEqual(originalTemplate, userTemplate)
  ) {
    return true;
  }
  // Check input_types containment
  if (
    originalTemplate &&
    userTemplate &&
    !inputTypesContained(originalTemplate, userTemplate)
  ) {
    return true;
  }
  return false;
};

export const checkCodeValidity = (
  data: NodeDataType,
  templates: { [key: string]: any },
) => {
  if (!data?.node || !templates) return;
  const template = templates[data.type]?.template;
  const currentCode = template?.code?.value;
  const thisNodesCode = data.node!.template?.code?.value;
  const originalOutputs = templates[data.type]?.outputs;
  const userOutputs = data.node?.outputs;
  const originalTemplate = template;
  const userTemplate = data.node?.template;
  const isOutdated = codeIsOutdated(currentCode, thisNodesCode, data.type);

  const hasBreakingChange = isOutdated
    ? codeHasBreakingChange(
        originalOutputs,
        userOutputs,
        originalTemplate,
        userTemplate,
      )
    : false;

  return {
    outdated: isOutdated,
    breakingChange: hasBreakingChange,
    userEdited: data.node?.edited ?? false,
  };
};

// templates[data.type]?.template is the original component while data.node.template is the user's component

// The codeIsOutdated function will have many checks to make sure the code is outdated
// the first check is if the current code is defined
// the second check is if the data.node.outputs are equal to templates[data.type]?.outputs
// and the data.node.template keys are equal to templates[data.type]?.template keys
// and all original input_types in each field are contained in the data.node.template input_types. If so, it means it won't break the component
// this is a breaking change so we will need to handle it

// Deep comparison for outputs (order-independent, returns object with per-output match status)
const outputsComparisonResult = (
  originalOutputs: OutputFieldType[] = [],
  userOutputs: OutputFieldType[] = [],
): { [outputName: string]: boolean } => {
  // Create a map for quick lookup by 'name'
  const userOutputMap = new Map<string, OutputFieldType>();
  userOutputs.forEach((output) => {
    userOutputMap.set(output.name, output);
  });

  // Build an object with per-output match status
  const result: { [outputName: string]: boolean } = {};

  originalOutputs.forEach((orig) => {
    const user = userOutputMap.get(orig.name);
    result[orig.name] =
      !!user &&
      orig.display_name === user.display_name &&
      JSON.stringify(orig.types) === JSON.stringify(user.types) &&
      orig.method === user.method &&
      orig.allows_loop === user.allows_loop;
  });

  // Check if all user outputs are present in original outputs
  userOutputs.forEach((user) => {
    if (!result[user.name]) {
      result[user.name] = false;
    }
  });

  return result;
};

const outputsAreEqual = (
  originalOutputs: OutputFieldType[],
  userOutputs: OutputFieldType[],
): boolean => {
  const result = outputsComparisonResult(originalOutputs, userOutputs);
  // Object.values is more direct for checking all values
  return Object.values(result).every(Boolean);
};

// Helper to check if all input_types in original are contained in user
const inputTypesContained = (
  originalTemplate: { [key: string]: any },
  userTemplate: { [key: string]: any },
): boolean => {
  for (const key of Object.keys(originalTemplate)) {
    const origField = originalTemplate[key];
    const userField = userTemplate[key];
    if (!userField) return false;
    if (origField.input_types) {
      const origTypes = Array.isArray(origField.input_types)
        ? origField.input_types
        : [];
      const userTypes = Array.isArray(userField.input_types)
        ? userField.input_types
        : [];
      if (!origTypes.every((t) => userTypes.includes(t))) {
        return false;
      }
    }
  }
  return true;
};

// Helper to check if template keys are equal
const templateKeysEqual = (
  originalTemplate: { [key: string]: any },
  userTemplate: { [key: string]: any },
): boolean => {
  const origKeys = Object.keys(originalTemplate).sort();
  const userKeys = Object.keys(userTemplate).sort();
  return JSON.stringify(origKeys) === JSON.stringify(userKeys);
};

export default checkCodeValidity;
