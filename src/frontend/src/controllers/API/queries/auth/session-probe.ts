import useAuthStore from "@/stores/authStore";

/**
 * Whether a session probe that answered `authenticated: false` may clear the
 * store's auth state.
 *
 * The probe answers for the cookie it was sent with. On a fresh auto-login
 * context it goes out before auto-login has set that cookie, so the backend
 * correctly says "not authenticated" — but the answer can land after login()
 * has already authenticated the page, and a failed probe resolves to the same
 * shape. Auto-login does not run again once it has settled, so honouring that
 * stale answer would leave every `enabled: isAuthenticated` query disabled
 * until a reload.
 *
 * Reads the store at call time: callers apply this from effects keyed on the
 * probe's data, not on auth state.
 */
export function canSessionProbeClearAuth(): boolean {
  return useAuthStore.getState().autoLogin !== true;
}
