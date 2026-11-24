import { componentsToIgnoreUpdate } from "@/constants/constants";
import type {
  APIClassType,
  APITemplateType,
  OutputFieldType,
} from "@/types/api";
import type { NodeDataType } from "../../types/flow";

export type CodeValidityType = {
  outdated: boolean;
  blocked: boolean;
  breakingChange: boolean;
  userEdited: boolean;
};

const transientTemplateKeys = new Set(["is_refresh", "tools_metadata"]);

// Synthetic output name a component receives when it is switched to tool mode. Must match
// TOOL_OUTPUT_NAME in src/lfx/src/lfx/base/tools/constants.py.
const TOOL_OUTPUT_NAME = "component_as_tool";

// Returns true when the saved node's outputs are the synthesized toolset output. Switching a
// component to tool mode replaces its authored outputs with this single entry, so they describe a
// runtime projection rather than anything the original component declares. Requires exactly one
// output: a malformed node carrying the name more than once is not something tool mode produces, so
// it keeps going through the authored-output comparison.
const nodeIsInToolMode = (userOutputs?: OutputFieldType[]): boolean =>
  !!userOutputs &&
  userOutputs.length === 1 &&
  userOutputs[0].name === TOOL_OUTPUT_NAME;

// Returns true when the original component can still be switched to tool mode: at least one input
// declares tool_mode. This is the input side of Component._handle_tool_mode, which is what creates
// the component_as_tool output at build time. The tool_mode flag on *outputs* marks which outputs a
// toolset exposes rather than the component's capability, so it is not used. checkHasToolMode in
// src/utils/reactflowUtils.ts answers a different question (whether to offer the toggle at all) and
// is not reused here.
const templateSupportsToolMode = (
  originalTemplate?: APITemplateType,
): boolean =>
  !!originalTemplate &&
  Object.values(originalTemplate).some((field) => Boolean(field?.tool_mode));

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
  originalTemplate?: APITemplateType,
  userTemplate?: APITemplateType,
): boolean => {
  // Check outputs
  if (nodeIsInToolMode(userOutputs)) {
    // A tool-mode node's saved outputs are the toolset projection, so they never match the
    // original component's declared outputs and comparing the two always reports a breaking
    // change. What matters for such a node is whether the component still supports tool mode. A
    // removed or renamed output cannot disconnect its edges, because its only output is the
    // toolset.
    if (!templateSupportsToolMode(originalTemplate)) {
      return true;
    }
  } else if (
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
    !templateKeysCompatible(originalTemplate, userTemplate)
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

/**
 * Whether an administrator's catalog policy blocks this component type.
 *
 * `blocked` only means "no template for this type", which is equally the
 * normal state of a user-authored component, an uninstalled bundle and a flow
 * imported from another install. Only the policy's own identities can tell
 * those apart, so the server sends them and this asks about *this* component
 * rather than whether some policy exists somewhere.
 */
export const isBlockedByCatalogPolicy = (
  blockedComponentTypes: ReadonlySet<string> | undefined,
  componentType: string | undefined,
): boolean =>
  componentType !== undefined &&
  blockedComponentTypes !== undefined &&
  blockedComponentTypes.has(componentType);

/**
 * Whether a missing template should stop the node running.
 *
 * Restricted mode blocks any unknown code-bearing node on its own, as before.
 * With custom components allowed, only an actual policy block makes one fatal
 * — otherwise a user's own component could not run.
 */
export const blockedStopsExecution = (
  allowCustomComponents: boolean,
  blockedComponentTypes: ReadonlySet<string> | undefined,
  componentType: string | undefined,
): boolean =>
  !allowCustomComponents ||
  isBlockedByCatalogPolicy(blockedComponentTypes, componentType);

export const checkCodeValidity = (
  data: NodeDataType,
  templates: { [key: string]: APIClassType },
  allowCustomComponents = true,
): CodeValidityType | undefined => {
  if (!data?.node || !templates) return;
  const template = templates[data.type]?.template;
  const currentCode = template?.code?.value;
  const thisNodesCode = data.node!.template?.code?.value;
  const originalOutputs = templates[data.type]?.outputs;
  const userOutputs = data.node?.outputs;
  const originalTemplate = template;
  const userTemplate = data.node?.template;
  const hasNodeCode =
    typeof thisNodesCode === "string" && thisNodesCode.length > 0;
  const isBlocked = hasNodeCode && !template;

  if (isBlocked) {
    return {
      outdated: false,
      blocked: true,
      breakingChange: false,
      userEdited: data.node?.edited ?? false,
    };
  }

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
    blocked: false,
    breakingChange: hasBreakingChange,
    userEdited: data.node?.edited ?? false,
  };
};

// templates[data.type]?.template is the original component while data.node.template is the user's component

// The codeIsOutdated function will have many checks to make sure the code is outdated
// the first check is if the current code is defined
// the second check is if the data.node.outputs are equal to templates[data.type]?.outputs
// and the data.node.template keys are compatible with templates[data.type]?.template keys
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
  originalTemplate: APITemplateType,
  userTemplate: APITemplateType,
): boolean => {
  for (const key of Object.keys(originalTemplate)) {
    const origField = originalTemplate[key];
    const userField = userTemplate[key];
    // A field the saved node predates has no saved edges feeding it; the rebuilt
    // template introduces it with its declared input_types, so there is nothing
    // to narrow.
    if (!userField) continue;
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

// Template key sets are compared directionally, not for equality. Must match
// _template_keys_compatible in src/lfx/src/lfx/upgrade/checker.py:
// - A field only the saved node has is one the current component dropped. Its stale
//   value is not read once the node is updated, so it cannot break the node.
// - A field only the current component has is one the saved node predates — the
//   evolution the contributing docs recommend as non-breaking. The update rebuilds
//   the template through /custom_component, which introduces the field with its
//   declared default, so it only breaks when that default is unusable: a *required*
//   field with nothing to fill it, which would turn a node that ran into one that
//   fails asking for input.
const templateKeysCompatible = (
  originalTemplate: APITemplateType,
  userTemplate: APITemplateType,
): boolean => {
  const isStructuralTemplateKey = (key: string) =>
    !key.startsWith("_") && !transientTemplateKeys.has(key);
  for (const key of Object.keys(originalTemplate)) {
    if (!isStructuralTemplateKey(key) || key in userTemplate) continue;
    const origField = originalTemplate[key];
    if (
      origField?.required &&
      (origField.value === undefined ||
        origField.value === null ||
        origField.value === "")
    ) {
      return false;
    }
  }
  return true;
};

export default checkCodeValidity;
