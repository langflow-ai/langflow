import type {
  QueryClient,
  QueryFilters,
  QueryKey,
} from "@tanstack/react-query";

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

/**
 * Refetches matching queries, including ones still loading their first page.
 *
 * `Query.fetch` only cancels and restarts an in-flight request when the query
 * already holds data. While `data` is still `undefined` it returns the
 * in-flight promise instead, so a refetch fired from a mutation resolves with
 * the response of a request that was issued *before* the mutation ran — the
 * newly created row never reaches the cache and nothing refetches afterwards.
 * Awaiting that cold fetch first turns the dedupe back into a real refetch.
 */
export const refetchQueriesFresh = async (
  queryClient: QueryClient,
  filters: QueryFilters,
): Promise<void> => {
  const coldFetches = queryClient
    .getQueryCache()
    .findAll(filters)
    .filter(
      (query) =>
        query.state.fetchStatus === "fetching" &&
        query.state.data === undefined,
    )
    .map((query) => query.promise?.catch(() => undefined));

  if (coldFetches.length > 0) {
    await Promise.all(coldFetches);
  }

  await queryClient.refetchQueries(filters);
};
