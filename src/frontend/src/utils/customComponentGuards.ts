import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import { useUtilityStore } from "@/stores/utilityStore";

function getStoredNode(nodeId: string) {
  const flowState = useFlowStore.getState();
  if (typeof flowState.getNode === "function") {
    return flowState.getNode(nodeId);
  }
  return flowState.nodes?.find((node) => node.id === nodeId);
}

/**
 * Checks whether a node is blocked by the custom-component policy and
 * should be skipped for API calls when custom components are not allowed.
 *
 * Two-layer check:
 * 1. Fast path via componentsToUpdate state
 * 2. Direct code comparison against templates (covers race where
 *    componentsToUpdate hasn't been populated yet)
 */
export function isNodeOutdated(
  nodeId: string,
  currentCodeValue?: string,
): boolean {
  const allowCustomComponents =
    useUtilityStore.getState().allowCustomComponents;
  if (allowCustomComponents) {
    return false;
  }

  // Fast path: check componentsToUpdate
  const componentsToUpdate = useFlowStore.getState().componentsToUpdate;
  const blockedEntry = componentsToUpdate.some(
    (c) => c.id === nodeId && (c.outdated || c.blocked) && !c.userEdited,
  );
  if (blockedEntry) return true;

  // Slow path: compare node code against server templates
  const nodeType = getStoredNode(nodeId)?.data?.type;
  if (nodeType === "CustomComponent") {
    return true;
  }

  if (nodeType && currentCodeValue !== undefined) {
    const templates = useTypesStore.getState().templates;
    const serverTemplate = templates[nodeType]?.template;
    if (!serverTemplate && currentCodeValue) {
      return true;
    }
    const serverCode = serverTemplate?.code?.value;
    if (serverCode && serverCode !== currentCodeValue) {
      return true;
    }
  }

  return false;
}

/**
 * Checks whether an API error is a 403 specifically from the backend
 * blocking a custom component (not an unrelated auth/permission error).
 */
// biome-ignore lint/suspicious/noExplicitAny: error objects have dynamic shape from axios
export function isCustomComponentBlockError(error: any): boolean {
  const e = error;
  return (
    e?.response?.status === 403 &&
    typeof e?.response?.data?.detail === "string" &&
    e.response.data.detail.includes("Custom component")
  );
}
