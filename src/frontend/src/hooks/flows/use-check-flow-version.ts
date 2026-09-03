import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import {
  attachTheirFlow,
  fetchAndAdoptServerVersion,
  readFlowVersionState,
  registerConflictState,
} from "./conflict-actions";

export type VersionCheck =
  | { outcome: "current" }
  | { outcome: "adopted"; author: string | null }
  | { outcome: "conflict" };

/**
 * Answers "is the flow on my screen still the flow on the server?".
 *
 * A save is not the only moment staleness matters — running is worse, because it
 * executes a version the flow no longer has and reports the result as if it were
 * current. Someone who has made no edits of their own has nothing to resolve, so
 * they get the newer version rather than a dialog.
 */
export const checkFlowVersion = async (
  flowId: string,
  currentUserId: string | null,
): Promise<VersionCheck> => {
  const baseline = useFlowsManagerStore.getState().currentFlow;
  if (!baseline || baseline.id !== flowId || !baseline.version_token) {
    return { outcome: "current" };
  }

  const state = await readFlowVersionState(flowId);
  if (!state?.version_token || state.version_token === baseline.version_token) {
    return { outcome: "current" };
  }

  // Whether the person edited, not whether the graph differs: hydration rewrites
  // nodes on every open, so a diff here turned a plain run into a conflict.
  if (!useFlowStore.getState().userEditedSinceLoad) {
    await fetchAndAdoptServerVersion(flowId);
    return { outcome: "adopted", author: state.last_modified_by_username };
  }

  registerConflictState({
    flowId,
    authorId: state.last_modified_by,
    authorName: state.last_modified_by_username,
    modifiedAt: state.updated_at,
    expectedToken: baseline.version_token,
    currentToken: state.version_token,
    currentUserId,
  });
  await attachTheirFlow(flowId);
  return { outcome: "conflict" };
};

/**
 * Raise a conflict when work was built on a version the server has moved past.
 *
 * Used after restoring a draft: the restored graph is unsaved work whose token is
 * older than the flow's, and nothing else would notice — the baseline reloaded
 * with the page is already current, so comparing against it finds nothing.
 */
export const raiseConflictForStaleWork = async (
  flowId: string,
  builtOnToken: string | null,
  currentUserId: string | null,
): Promise<boolean> => {
  if (!builtOnToken) return false;

  const state = await readFlowVersionState(flowId);
  if (!state?.version_token || state.version_token === builtOnToken) {
    return false;
  }

  registerConflictState({
    flowId,
    authorId: state.last_modified_by,
    authorName: state.last_modified_by_username,
    modifiedAt: state.updated_at,
    expectedToken: builtOnToken,
    currentToken: state.version_token,
    currentUserId,
  });
  await attachTheirFlow(flowId);
  return true;
};
