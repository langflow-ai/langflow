import type { QueryClient, QueryFilters } from "@tanstack/react-query";

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
