import {
  componentsToIgnoreUpdate,
  TYPE_MIGRATIONS,
} from "@/constants/constants";
import type {
  APIClassType,
  APITemplateType,
  OutputFieldType,
} from "@/types/api";
import type { EdgeType, NodeDataType } from "../../types/flow";

export type CodeValidityType = {
  outdated: boolean;
  blocked: boolean;
  breakingChange: boolean;
  userEdited: boolean;
  // The current component is retired. The editor refuses to run it in every mode, edited or not: an
  // edit usually keeps the retired imports or base class, and a dismissed update keeps shipped code
  // that the runtime maps to the retired class.
  retired: boolean;
  retiredIn?: string;
  replacement?: string[];
};

// Template keys that are editor runtime metadata, not component fields. Must be the same set as
// TRANSIENT_TEMPLATE_KEYS in src/lfx/src/lfx/upgrade/checker.py.
const transientTemplateKeys = new Set(["is_refresh", "tools_metadata"]);

const isStructuralTemplateKey = (key: string) =>
  !key.startsWith("_") && !transientTemplateKeys.has(key);

// A type list as a set, with historical type names (Data, DataFrame) mapped to their current
// names (JSON, Table): an edge saved with the old name still connects.
const canonicalTypes = (types: unknown): Set<string> =>
  new Set(
    (Array.isArray(types) ? types : []).map((t) => TYPE_MIGRATIONS[t] ?? t),
  );

const isSubset = (inner: Set<string>, outer: Set<string>): boolean =>
  [...inner].every((t) => outer.has(t));

// The field an edge goes into, from data.targetHandle when it is an object, else the escaped handle
// string, or a legacy "type|field|node id" string, which the runtime still reads. Must match
// _target_handle in src/lfx/src/lfx/upgrade/checker.py.
const targetFieldName = (edge: EdgeType): string | undefined => {
  const handle = edge.data?.targetHandle;
  if (handle && typeof handle === "object" && !Array.isArray(handle))
    return handle.fieldName;
  try {
    return JSON.parse((edge.targetHandle ?? "").replace(/œ/g, '"'))?.fieldName;
  } catch {
    return (edge.targetHandle ?? "").split("|")[1];
  }
};

// Maps each node id to the fields a connection goes into. Must match _connected_fields_by_node in
// src/lfx/src/lfx/upgrade/checker.py.
export const connectedFieldsByNode = (
  edges: EdgeType[],
): Map<string, Set<string>> => {
  const connected = new Map<string, Set<string>>();
  for (const edge of edges) {
    const fieldName = targetFieldName(edge);
    if (!fieldName) continue;
    if (!connected.has(edge.target)) connected.set(edge.target, new Set());
    connected.get(edge.target)!.add(fieldName);
  }
  return connected;
};

// The fields the saved node lists in custom_fields. A Prompt saves {"template": ["question", ...]}:
// one field per template variable, which the component rebuilds when the node is updated.
const customFieldNames = (data: NodeDataType): Set<string> =>
  new Set(
    Object.values(data.node?.custom_fields ?? {}).flatMap((names) =>
      Array.isArray(names) ? names : [],
    ),
  );

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

// Returns true if there is a breaking change (outputs, template keys, or shared fields). A change
// is breaking when updating the node drops a connection, drops a value, or needs input nobody gave.
// Must match has_breaking_change in src/lfx/src/lfx/upgrade/checker.py; both run the shared cases in
// src/lfx/tests/data/component_compat/cases.json.
const codeHasBreakingChange = (
  originalOutputs: OutputFieldType[] = [],
  userOutputs: OutputFieldType[] | undefined,
  originalTemplate: APITemplateType | undefined,
  userTemplate: APITemplateType | undefined,
  customFields: Set<string>,
  connectedFields: ReadonlySet<string> | undefined,
): boolean => {
  // Without saved outputs nothing tells which outputs had edges, so assume they all did.
  if (!userOutputs && originalOutputs.length > 0) return true;
  // Check outputs
  const inToolMode = nodeIsInToolMode(userOutputs);
  if (inToolMode) {
    // A tool-mode node's saved outputs are the toolset projection, so they never match the
    // original component's declared outputs and comparing the two always reports a breaking
    // change. What matters for such a node is whether the component still supports tool mode. A
    // removed or renamed output cannot disconnect its edges, because its only output is the
    // toolset.
    if (!templateSupportsToolMode(originalTemplate)) {
      return true;
    }
  } else if (!outputsCompatible(originalOutputs, userOutputs ?? [])) {
    return true;
  }
  // Check template keys
  if (
    originalTemplate &&
    userTemplate &&
    !templateKeysCompatible(originalTemplate, userTemplate, customFields)
  ) {
    return true;
  }
  // Check fields both sides have
  if (
    originalTemplate &&
    userTemplate &&
    !sharedFieldsCompatible(
      originalTemplate,
      userTemplate,
      connectedFields,
      inToolMode,
    )
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

// connectedFields names the fields a connection goes into (see connectedFieldsByNode). Leaving it
// undefined means the connections are unknown, so every field counts as connected.
export const checkCodeValidity = (
  data: NodeDataType,
  templates: { [key: string]: APIClassType },
  allowCustomComponents = true,
  connectedFields?: ReadonlySet<string>,
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
  // As in _classify_node in src/lfx/src/lfx/upgrade/checker.py: only a node with code and a type
  // that is not ignored can be retired, and a retired entry wins before its template is read.
  const retiredIn =
    hasNodeCode && !componentsToIgnoreUpdate.includes(data.type)
      ? templates[data.type]?.retired_in
      : undefined;
  const isBlocked = hasNodeCode && !template && !retiredIn;

  if (isBlocked) {
    return {
      outdated: false,
      blocked: true,
      breakingChange: false,
      userEdited: data.node?.edited ?? false,
      retired: false,
    };
  }

  const isOutdated = codeIsOutdated(currentCode, thisNodesCode, data.type);

  const hasBreakingChange = isOutdated
    ? codeHasBreakingChange(
        originalOutputs,
        userOutputs,
        originalTemplate,
        userTemplate,
        customFieldNames(data),
        connectedFields,
      )
    : false;

  return {
    outdated: isOutdated,
    blocked: false,
    breakingChange: hasBreakingChange,
    userEdited: data.node?.edited ?? false,
    retired: !!retiredIn,
    ...(retiredIn && {
      retiredIn,
      replacement: templates[data.type]?.replacement ?? [],
    }),
  };
};

// templates[data.type]?.template is the original component while data.node.template is the user's component

// Every output the saved node has must still exist with the same method and loop setting, and may
// produce more types than the saved node knew (aliases applied), never fewer. An added output and a
// display name change are safe. Must match _outputs_are_compatible in
// src/lfx/src/lfx/upgrade/checker.py.
const outputsCompatible = (
  originalOutputs: OutputFieldType[],
  userOutputs: OutputFieldType[],
): boolean =>
  userOutputs.every((user) => {
    const orig = originalOutputs.find((output) => output.name === user.name);
    return (
      !!orig &&
      isSubset(canonicalTypes(user.types), canonicalTypes(orig.types)) &&
      orig.method === user.method &&
      orig.allows_loop === user.allows_loop
    );
  });

// A saved field holds a value unless the value is undefined, null, "", [] or {}.
const holdsValue = (value: unknown): boolean =>
  value !== undefined &&
  value !== null &&
  value !== "" &&
  !(Array.isArray(value) && value.length === 0) &&
  !(
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value).length === 0
  );

// Fields both sides have must keep their saved edges and saved values. Must match
// _shared_fields_compatible in src/lfx/src/lfx/upgrade/checker.py. Undefined connectedFields
// means the connections are unknown, so every field counts as connected.
// - A changed field type is breaking when an edge goes into the field, because cleanEdges keeps
//   an edge only when the handle's field type is equal. It is also breaking when the saved field
//   holds a value, because the update copies a saved value only when the field type is equal.
// - Every type a connected field accepted must still be accepted (aliases applied). Narrowing
//   drops the saved edges, and an emptied input_types list means the field takes no connections
//   at all. Widening is safe.
// - On a node in tool mode, a connected field the component now marks tool_mode is breaking:
//   cleanEdges drops edges into tool-mode fields of a tool-mode node.
const sharedFieldsCompatible = (
  originalTemplate: APITemplateType,
  userTemplate: APITemplateType,
  connectedFields: ReadonlySet<string> | undefined,
  inToolMode: boolean,
): boolean => {
  for (const key of Object.keys(userTemplate)) {
    if (!isStructuralTemplateKey(key) || !Object.hasOwn(originalTemplate, key))
      continue;
    const origField = originalTemplate[key];
    const userField = userTemplate[key];
    if (
      !origField ||
      !userField ||
      typeof origField !== "object" ||
      typeof userField !== "object"
    )
      continue;
    const connected = !connectedFields || connectedFields.has(key);
    if (
      origField.type !== userField.type &&
      (connected || holdsValue(userField.value))
    )
      return false;
    if (!connected) continue;
    if (
      !isSubset(
        canonicalTypes(userField.input_types),
        canonicalTypes(origField.input_types),
      )
    ) {
      return false;
    }
    if (inToolMode && origField.tool_mode && !userField.tool_mode) return false;
  }
  return true;
};

// Template key sets are compared directionally, not for equality. Must match
// _template_keys_compatible in src/lfx/src/lfx/upgrade/checker.py:
// - A field only the saved node has is one the current component dropped, or one the
//   component added while it was edited (Run Flow inputs, MCP Tools arguments). The update
//   drops the field, its value, and any edge into it, so it is always breaking, connected or not.
//   The exception is a field the node lists in custom_fields (Prompt variables), which the
//   component rebuilds.
// - A field only the current component has is one the saved node predates — the
//   evolution the contributing docs recommend as non-breaking. The update rebuilds
//   the template through /custom_component, which introduces the field with its
//   declared default, so it only breaks when that default is unusable: a *required*
//   field with nothing to fill it, which would turn a node that ran into one that
//   fails asking for input.
const templateKeysCompatible = (
  originalTemplate: APITemplateType,
  userTemplate: APITemplateType,
  customFields: Set<string>,
): boolean => {
  for (const key of Object.keys(userTemplate)) {
    if (
      isStructuralTemplateKey(key) &&
      !Object.hasOwn(originalTemplate, key) &&
      !customFields.has(key)
    ) {
      return false;
    }
  }
  for (const key of Object.keys(originalTemplate)) {
    if (!isStructuralTemplateKey(key) || Object.hasOwn(userTemplate, key))
      continue;
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
