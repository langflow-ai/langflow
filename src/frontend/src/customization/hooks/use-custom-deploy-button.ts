/** Lets a deployment block the Deploy button and say why (already translated). OSS never blocks it. */
export type DeployButtonState = { blockedReason: string | null };

// Default seam: OSS never blocks the Deploy button.
export function useCustomDeployButton(): DeployButtonState {
  return { blockedReason: null };
}
