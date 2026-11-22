/**
 * Lets a deployment block the new-project button and say why (already translated). OSS never blocks it.
 * The full reason goes in the tooltip and the accessible description.
 */
export type NewProjectButtonState = {
  blockedReason: string | null;
  /** Short line shown under the Projects header while blocked. Falls back to blockedReason. */
  blockedHint?: string | null;
};

// Default seam: OSS never blocks the new-project button.
export function useCustomNewProjectButton(): NewProjectButtonState {
  return { blockedReason: null };
}
