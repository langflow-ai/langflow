export type PlaygroundAuthState = "loading" | "allowed";

/**
 * Decide whether the direct-link playground may render yet.
 *
 * Note what is *not* an input: `autoLogin`. The gate used to send any
 * unauthenticated visitor to `/login` whenever auto-login was disabled, which
 * made public direct links unreachable for anonymous visitors on exactly the
 * deployments where anonymity is meaningful — the page never got to ask the
 * server whether the flow was public. Whether a flow is publicly reachable is a
 * server-side authorization decision, not an authentication one, so the gate
 * only waits for session hydration and lets the page make that call. A flow
 * that turns out not to be public still routes to `/login` with the link
 * preserved, from the page's own unreachable-flow path.
 *
 * Kept in its own module so tests can import the real decision instead of
 * re-deriving it — the gate component pulls in assets jest cannot resolve.
 */
export function computePlaygroundAuthState({
  isAuthenticated,
  isAutoLoginFetched,
  isSessionProcessed,
}: {
  isAuthenticated: boolean;
  isAutoLoginFetched: boolean;
  isSessionProcessed: boolean;
}): PlaygroundAuthState {
  const isAuthCheckComplete =
    (isAutoLoginFetched || isAuthenticated) && isSessionProcessed;
  return isAuthCheckComplete ? "allowed" : "loading";
}
