import type { UseMutationResult } from "@tanstack/react-query";
import { cloneDeep, debounce, isEqual } from "lodash";
import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import type {
  APIClassType,
  APITemplateType,
  ResponseErrorDetailAPI,
} from "@/types/api";
import i18n from "../../i18n";
import { updateHiddenOutputs } from "./update-hidden-outputs";

const debouncedFunctions = new Map<string, ReturnType<typeof debounce>>();

const getNodeTemplate = (nodeId: string): APITemplateType | undefined => {
  const currentNode = useFlowStore
    .getState()
    .nodes.find((flowNode) => flowNode.id === nodeId);
  return currentNode?.data?.node?.template;
};

const getNodeCode = (nodeId: string): unknown => {
  return getNodeTemplate(nodeId)?.code?.value;
};

// Canvas visibility and API exposure are owned by the user through the
// Parameters panel, never by a refresh. The response carries whatever these
// were when the request left, so applying it wholesale reverts a flag the
// user flipped meanwhile - the field vanishes off the node with no feedback.
const USER_OWNED_FIELD_FLAGS = ["advanced", "api_editable"] as const;

// The field values the last applied response wrote, per node. A store value
// that no longer matches this baseline was changed locally, which is what makes
// an older in-flight response stale for that field. Comparing against the
// baseline rather than the request snapshot keeps concurrent refreshes working:
// several mount refreshes share one snapshot, so the first response to land
// would otherwise look like a local edit and suppress the others.
const lastAppliedValues = new Map<string, Record<string, unknown>>();
const LAST_APPLIED_PRUNE_THRESHOLD = 100;

const rememberAppliedValues = (
  nodeId: string,
  template: APITemplateType,
): void => {
  if (lastAppliedValues.size > LAST_APPLIED_PRUNE_THRESHOLD) {
    const liveIds = new Set(useFlowStore.getState().nodes.map((n) => n.id));
    for (const id of lastAppliedValues.keys()) {
      if (!liveIds.has(id)) lastAppliedValues.delete(id);
    }
  }
  const values: Record<string, unknown> = {};
  for (const [fieldName, field] of Object.entries(template)) {
    if (typeof field === "object" && field !== null) {
      values[fieldName] = cloneDeep(field.value);
    }
  }
  lastAppliedValues.set(nodeId, values);
};

// LE-2272: a response answers for the field values that were current when the
// request left. Anything the user edited meanwhile (a tool action's slug,
// description or approval_actions; any field typed while a refresh is in
// flight) is newer than the response, so the local value wins. When the user
// did not touch the field, the backend value still applies - a legitimate
// refresh that recomputes a value is unaffected.
const keepUserEdits = (
  nodeId: string,
  requestedTemplate: APITemplateType | undefined,
  incomingTemplate: APITemplateType,
): APITemplateType => {
  const currentTemplate = getNodeTemplate(nodeId);
  if (!requestedTemplate || !currentTemplate) return incomingTemplate;

  const merged = cloneDeep(incomingTemplate);
  const baseline = lastAppliedValues.get(nodeId);
  for (const [fieldName, currentField] of Object.entries(currentTemplate)) {
    const requestedField = requestedTemplate[fieldName];
    const incomingField = merged[fieldName];
    if (
      typeof currentField !== "object" ||
      currentField === null ||
      typeof requestedField !== "object" ||
      requestedField === null ||
      typeof incomingField !== "object" ||
      incomingField === null
    ) {
      continue;
    }
    for (const flag of USER_OWNED_FIELD_FLAGS) {
      if (currentField[flag] !== requestedField[flag]) {
        incomingField[flag] = currentField[flag];
      }
    }
    const appliedValue =
      baseline && fieldName in baseline
        ? baseline[fieldName]
        : requestedField.value;
    if (!isEqual(currentField.value, appliedValue)) {
      incomingField.value = cloneDeep(currentField.value);
    }
  }
  return merged;
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
              template: node.template,
              field_name: parameterName,
              tool_mode: toolMode ?? node.tool_mode,
              is_refresh: isRefresh ?? false,
            });
            if (newTemplate && !isStaleForNode(nodeId, node)) {
              newNode.template = keepUserEdits(
                nodeId,
                node.template,
                newTemplate.template,
              );
              rememberAppliedValues(nodeId, newNode.template);
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
