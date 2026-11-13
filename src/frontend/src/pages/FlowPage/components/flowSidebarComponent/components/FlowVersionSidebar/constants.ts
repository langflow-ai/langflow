export const CURRENT_DRAFT_ID = "__current_draft__";

// Timeline entries are selected by the revision a preview or restore shows,
// under a prefix no version id can have.
export const REVISION_ID_PREFIX = "revision:";

export function revisionSelectionId(revision: number): string {
  return `${REVISION_ID_PREFIX}${revision}`;
}

export function revisionOfSelection(id: string | null): number | null {
  if (!id?.startsWith(REVISION_ID_PREFIX)) return null;
  const revision = Number(id.slice(REVISION_ID_PREFIX.length));
  return Number.isInteger(revision) ? revision : null;
}
