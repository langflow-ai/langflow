import { useCallback } from "react";
import useAuthStore from "@/stores/authStore";

/**
 * Returns a check that says whether a resource's owner id is the signed-in
 * user. A missing owner id or a not-yet-loaded user counts as owned, so an
 * ownership filter never hides rows it can't judge.
 */
export function useIsOwnedByCurrentUser(): (
  ownerId: string | null | undefined,
) => boolean {
  const currentUserId = useAuthStore((state) => state.userData?.id);
  return useCallback(
    (ownerId) => !ownerId || !currentUserId || ownerId === currentUserId,
    [currentUserId],
  );
}
