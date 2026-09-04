import type { FlowType } from "@/types/flow";

/**
 * Whether the shareable playground may be opened for this flow.
 *
 * The playground is an execution surface: it always builds through the
 * anonymous `build_public_tmp` endpoint, so the only capability that makes the
 * page usable is public execution.
 *
 * `public_access` is the authorization layer's own answer, returned by
 * `GET /api/v1/flows/public_flow/{id}`. Prefer it: a canonical
 * `AuthzShare(scope=public)` admits flows whose `access_type` is still PRIVATE,
 * and a `read`-level share bounds an `access_type=PUBLIC` flow back to
 * read-only. The legacy flag disagrees with the backend in both directions.
 *
 * The fallback covers flows that reached the page from a source that carries no
 * capability set — an already-populated flow store rather than the direct-link
 * fetch. Those payloads only have the legacy flag to go on. It is a rendering
 * hint either way; every build still authorizes itself server-side.
 */
export function canOpenPublicPlayground(
  flow: Pick<FlowType, "access_type" | "public_access"> | undefined | null,
): boolean {
  if (!flow) return false;
  if (flow.public_access) return flow.public_access.can_execute;
  return flow.access_type === "PUBLIC";
}

/**
 * Where to send a visitor whose direct link did not resolve to a playground.
 *
 * The route gate no longer pre-empts this with a blanket login redirect, since
 * that made public links unreachable for anonymous visitors whenever auto-login
 * was disabled. The link is only known to be unusable once the server has
 * declined it, so the choice of destination lands here instead.
 *
 * An anonymous visitor on a login-required deployment may simply be looking at
 * a flow that is not public — sign-in is the useful next step, and the link is
 * preserved as the redirect target so they land back here afterwards. Everyone
 * else (already signed in, or auto-login deployments) goes home.
 */
export function unreachablePlaygroundDestination({
  flowId,
  autoLogin,
  isAuthenticated,
}: {
  flowId: string | undefined;
  autoLogin: boolean | null;
  isAuthenticated: boolean;
}): string {
  if (flowId && autoLogin === false && !isAuthenticated) {
    return `/login?redirect=/playground/${flowId}/`;
  }
  return "/";
}
