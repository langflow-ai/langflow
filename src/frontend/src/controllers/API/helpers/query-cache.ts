import type { QueryClient, QueryKey } from "@tanstack/react-query";

/**
 * Returns true only when an exact cache entry is a settled, successful
 * snapshot. Invalidated or actively fetching data may belong to a revoked or
 * changed authorization scope and must not drive security-sensitive UI or
 * cleanup decisions.
 */
export const isSettledSuccessfulQuery = (
  queryClient: QueryClient,
  queryKey: QueryKey,
): boolean => {
  const state = queryClient.getQueryState(queryKey);
  return (
    state?.status === "success" &&
    state.fetchStatus === "idle" &&
    state.isInvalidated === false
  );
};

export const getSettledSuccessfulQueryData = <T>(
  queryClient: QueryClient,
  queryKey: QueryKey,
): T | undefined => {
  if (!isSettledSuccessfulQuery(queryClient, queryKey)) {
    return undefined;
  }
  return queryClient.getQueryData<T>(queryKey);
};
