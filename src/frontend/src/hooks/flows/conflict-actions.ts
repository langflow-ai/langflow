import { cloneDeep } from "lodash";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { saveConflictDraft } from "@/utils/conflict-draft";
import { processFlows } from "@/utils/reactflowUtils";

/**
 * The two things every conflict path has to do, in one place.
 *
 * A refused save and a stale-version check reach the same two conclusions —
 * "take their version" or "raise the conflict" — and each had its own copy. The
 * copies had already drifted apart in error handling, which is how the adopt path
 * came to advance the baseline without moving the canvas with it.
 */

export type FlowVersionState = {
  version_token: string | null;
  last_modified_by: string | null;
  last_modified_by_username: string | null;
  updated_at: string | null;
};

export const readFlowVersionState = async (
  flowId: string,
): Promise<FlowVersionState | null> => {
  try {
    const response = await api.get<FlowVersionState>(
      `${getURL("FLOWS")}/${flowId}/version-state`,
    );
    return response.data;
  } catch {
    // A check that cannot run must never block the action it was guarding.
    return null;
  }
};

/**
 * Move the canvas and the baseline to the server's version together.
 *
 * Never one without the other: advancing only the baseline leaves the stale graph
 * on screen looking like an unsaved edit, and the next autosave pushes it back
 * over the work this was meant to preserve.
 */
export const adoptServerVersion = (serverFlow: FlowType): void => {
  const adopted = cloneDeep(serverFlow);
  processFlows([adopted]);
  useFlowsManagerStore.getState().setCurrentFlow(adopted);
};

export const fetchAndAdoptServerVersion = async (
  flowId: string,
): Promise<boolean> => {
  try {
    const fresh = await api.get<FlowType>(`${getURL("FLOWS")}/${flowId}`);
    adoptServerVersion(fresh.data);
    return true;
  } catch {
    return false;
  }
};

type ConflictAuthorship = {
  flowId: string;
  authorId: string | null;
  authorName: string | null;
  modifiedAt: string | null;
  expectedToken: string | null;
  currentToken: string | null;
  currentUserId: string | null;
};

export const registerConflictState = ({
  flowId,
  authorId,
  authorName,
  modifiedAt,
  expectedToken,
  currentToken,
  currentUserId,
}: ConflictAuthorship): void => {
  useFlowConflictStore.getState().setConflict({
    flowId,
    author: { id: authorId, username: authorName },
    isSelf: authorId !== null && authorId === currentUserId,
    modifiedAt,
    expectedToken,
    currentToken,
    theirFlow: null,
  });
  persistConflictDraft(flowId, expectedToken, currentUserId);
};

/**
 * Keep the stranded work somewhere a reload cannot take it.
 *
 * Here rather than in the save path because a refused save is only one of the ways
 * a conflict is found: the pre-run version check and a restored draft reach the
 * same state, and neither wrote a draft — so the work those two protected existed
 * in the tab and nowhere else. Once a conflict stands, ``saveFlow`` refuses to run
 * at all, so this is also the only place that can keep the draft current.
 */
export const persistConflictDraft = (
  flowId: string,
  builtOnToken: string | null,
  currentUserId: string | null,
): void => {
  const live = useFlowStore.getState();
  const liveFlow = live.currentFlow;
  if (liveFlow?.id !== flowId) return;
  saveConflictDraft(
    currentUserId,
    {
      ...liveFlow,
      data: { ...liveFlow.data, nodes: live.nodes, edges: live.edges },
    } as FlowType,
    builtOnToken,
  );
};

/** Fetch the other version so the dialog can diff against it; the dialog degrades without it. */
export const attachTheirFlow = async (flowId: string): Promise<void> => {
  try {
    const fresh = await api.get<FlowType>(`${getURL("FLOWS")}/${flowId}`);
    useFlowConflictStore.getState().setTheirFlow(fresh.data);
  } catch {
    // Leaves the dialog listing my changes only, which still duplicates.
  }
};

/**
 * Re-registers a conflict after the flow moved again, tokens and all.
 *
 * ``registerConflictState`` deliberately keeps the first conflict for a flow so a
 * dialog someone is reading does not change author mid-sentence. A refused
 * overwrite is the one case where the standing conflict is the problem: its token
 * is the one the server just rejected.
 */
export const refreshConflictState = (input: ConflictAuthorship): void => {
  const {
    flowId,
    authorId,
    authorName,
    modifiedAt,
    expectedToken,
    currentToken,
    currentUserId,
  } = input;
  useFlowConflictStore.getState().refreshConflict({
    flowId,
    author: { id: authorId, username: authorName },
    isSelf: authorId !== null && authorId === currentUserId,
    modifiedAt,
    expectedToken,
    currentToken,
    theirFlow: null,
  });
};
