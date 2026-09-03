import type { FlowType } from "@/types/flow";
import { removeApiKeys } from "@/utils/reactflowUtils";

/**
 * Keeps unsaved work alive when a save has been refused.
 *
 * Between the refusal and the duplicate, the only copy of someone's work is the
 * tab. That gap can last minutes while they read a diff and decide, and a reload
 * in the middle of it used to lose everything.
 *
 * The draft is offered back, never applied automatically: silently resurrecting
 * work drops people into a conflict they did not ask to re-enter.
 */

export type ConflictDraft = {
  flowId: string;
  userId: string;
  /** The version the draft was built on; the next save will conflict again, correctly. */
  versionToken: string | null;
  savedAt: string;
  data: FlowType["data"];
  /** True when the scrubber cleared secret fields, so the restore can say so. */
  secretsCleared: boolean;
};

// Comfortably above the largest flow measured (342 KB) and well under the point
// where a single key threatens the origin's quota.
const MAX_DRAFT_BYTES = 2_000_000;

const key = (userId: string, flowId: string) => `lf_draft_${userId}_${flowId}`;

type TemplateField = { value?: unknown };
type GraphNode = {
  id?: string;
  data?: { node?: { template?: Record<string, TemplateField> } };
};

const templatesOf = (flow: FlowType): Record<string, TemplateField>[] =>
  ((flow.data?.nodes ?? []) as unknown as GraphNode[])
    .map((node) => node.data?.node?.template)
    .filter((template): template is Record<string, TemplateField> =>
      Boolean(template),
    );

/**
 * Whether the scrubber actually removed something, by comparing what it produced
 * against what it was given.
 *
 * Asking the input instead ("does any field say password") got this wrong twice
 * over: `removeApiKeys` deliberately preserves an `api_key` holding a global
 * variable name, so the restore claimed fields needed re-entering when they did
 * not — and answering it meant serialising the whole graph twice on a path that
 * runs while somebody is waiting mid-conflict.
 */
const anyValueWasCleared = (
  original: FlowType,
  scrubbed: FlowType,
): boolean => {
  const before = templatesOf(original);
  const after = templatesOf(scrubbed);
  return before.some((template, index) =>
    Object.keys(template).some(
      (name) => template[name]?.value !== after[index]?.[name]?.value,
    ),
  );
};

/**
 * Store the draft. Never throws: a browser that refuses to store must not also
 * break the conflict dialog, which is the exit that has to keep working.
 */
export const saveConflictDraft = (
  userId: string | null | undefined,
  flow: FlowType,
  versionToken: string | null,
): boolean => {
  if (!userId || !flow?.id) return false;
  try {
    const scrubbed = removeApiKeys({ ...flow });
    const draft: ConflictDraft = {
      flowId: flow.id,
      userId,
      versionToken,
      savedAt: new Date().toISOString(),
      data: scrubbed.data,
      secretsCleared: anyValueWasCleared(flow, scrubbed),
    };
    const payload = JSON.stringify(draft);
    if (payload.length > MAX_DRAFT_BYTES) return false;
    localStorage.setItem(key(userId, flow.id), payload);
    return true;
  } catch {
    return false;
  }
};

/** The draft for this person and this flow, or null. Another user's is never returned. */
export const readConflictDraft = (
  userId: string | null | undefined,
  flowId: string | null | undefined,
): ConflictDraft | null => {
  if (!userId || !flowId) return null;
  try {
    const raw = localStorage.getItem(key(userId, flowId));
    if (!raw) return null;
    const draft = JSON.parse(raw) as ConflictDraft;
    if (draft.userId !== userId || draft.flowId !== flowId) return null;
    if (!draft.data?.nodes) return null;
    return draft;
  } catch {
    return null;
  }
};

export const clearConflictDraft = (
  userId: string | null | undefined,
  flowId: string | null | undefined,
): void => {
  if (!userId || !flowId) return;
  try {
    localStorage.removeItem(key(userId, flowId));
  } catch {
    // A browser that will not let us clear it will not have let us write it.
  }
};

/** Drop every draft on this browser, so logging out never leaves work for the next person. */
export const clearAllConflictDrafts = (): void => {
  try {
    const doomed = Object.keys(localStorage).filter((name) =>
      name.startsWith("lf_draft_"),
    );
    for (const name of doomed) localStorage.removeItem(name);
  } catch {
    // Nothing to clean up if storage is unavailable.
  }
};
