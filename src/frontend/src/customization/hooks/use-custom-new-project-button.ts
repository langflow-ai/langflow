/** Lets a deployment block the new-project button and say why (already translated). OSS never blocks it. */
export type NewProjectButtonState = { blockedReason: string | null };

// Default seam: OSS never blocks the new-project button.
export function useCustomNewProjectButton(): NewProjectButtonState {
  return { blockedReason: null };
}
