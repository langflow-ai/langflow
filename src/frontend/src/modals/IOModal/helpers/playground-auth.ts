import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";

/**
 * Checks if the current context is an authenticated user on the shareable playground.
 * Used to determine whether to use the DB-backed API or sessionStorage for messages.
 *
 * Requires userData.id to be loaded — otherwise falls back to anonymous mode
 * to avoid UUID mismatch between frontend and backend.
 */
export function isAuthenticatedPlayground(): boolean {
  const isPlayground = useFlowStore.getState().playgroundPage;
  const { isAuthenticated, autoLogin, userData } = useAuthStore.getState();
  // Use `autoLogin === false` (not `!autoLogin`) to avoid race condition
  // when autoLogin is still null (unresolved) — treat null same as true.
  return (
    isPlayground && isAuthenticated && autoLogin === false && !!userData?.id
  );
}
