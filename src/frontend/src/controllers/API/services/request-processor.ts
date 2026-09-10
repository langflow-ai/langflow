import {
  type QueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import axios from "axios";
import type {
  MutationFunctionType,
  QueryFunctionType,
} from "../../../types/api";

const MAX_MUTATION_RETRIES = 3;
const MAX_RETRY_DELAY_MS = 30000;

// 4xx responses are intentional client-side rejections (auth, validation,
// deployment guards, etc.) and won't change on retry.
function isClientError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false;
  const status = error.response?.status;
  return typeof status === "number" && status >= 400 && status < 500;
}

// Transient failures worth replaying: 5xx responses and requests that got no
// response at all (network drop, timeout). Cancellations and request-setup
// errors settle immediately.
export function isRetryableServerError(error: unknown): boolean {
  if (!axios.isAxiosError(error) || axios.isCancel(error)) return false;
  const status = error.response?.status;
  if (typeof status === "number") return status >= 500;
  return error.request != null;
}

// Retry-After is either delta-seconds or an HTTP-date (RFC 9110 §10.2.3).
export function getRetryAfterMs(error: unknown): number | undefined {
  if (!axios.isAxiosError(error)) return undefined;
  const header = error.response?.headers?.["retry-after"];
  if (header == null || header === "") return undefined;
  const seconds = Number(header);
  if (Number.isFinite(seconds)) {
    return Math.min(Math.max(seconds, 0) * 1000, MAX_RETRY_DELAY_MS);
  }
  const date = Date.parse(String(header));
  if (Number.isNaN(date)) return undefined;
  return Math.min(Math.max(date - Date.now(), 0), MAX_RETRY_DELAY_MS);
}

function makeRetry(maxRetries: number) {
  return (failureCount: number, error: unknown) => {
    if (isClientError(error)) return false;
    return failureCount < maxRetries;
  };
}

const queryRetry = makeRetry(5);

const retryDelay = (attemptIndex: number) =>
  Math.min(1000 * 2 ** attemptIndex, MAX_RETRY_DELAY_MS);

const sleep = (ms: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms));

function getMutationRetryDelayMs(
  error: unknown,
  attempt: number,
  customRetryDelay: UseMutationOptions["retryDelay"],
): number {
  if (typeof customRetryDelay === "function") {
    return customRetryDelay(attempt, error as Error);
  }
  if (typeof customRetryDelay === "number") {
    return customRetryDelay;
  }
  return getRetryAfterMs(error) ?? retryDelay(attempt);
}

// Mutation retries must run inside the mutation function rather than through
// react-query's `retry` option: the retryer pauses between attempts whenever
// the document is hidden or the browser reports offline, so a failing
// mutation can sit in that paused state forever — it never settles, the
// caller's onError never fires, and the user gets no feedback for a 5xx.
// A plain setTimeout keeps ticking in hidden tabs, and the mutation stays in
// an ordinary pending state until it resolves or throws, which guarantees
// onError/onSettled run once the retry budget is spent.
export function withTransientErrorRetry<TArgs extends unknown[], TData>(
  mutationFn: (...args: TArgs) => Promise<TData>,
  maxRetries: number = MAX_MUTATION_RETRIES,
  customRetryDelay?: UseMutationOptions["retryDelay"],
): (...args: TArgs) => Promise<TData> {
  return async (...args: TArgs) => {
    for (let attempt = 0; ; attempt++) {
      try {
        return await mutationFn(...args);
      } catch (error) {
        if (attempt >= maxRetries || !isRetryableServerError(error)) {
          throw error;
        }
        await sleep(getMutationRetryDelayMs(error, attempt, customRetryDelay));
      }
    }
  };
}

export function UseRequestProcessor(): {
  query: QueryFunctionType;
  mutate: MutationFunctionType;
  queryClient: QueryClient;
} {
  const queryClient = useQueryClient();

  function query(
    queryKey: UseQueryOptions["queryKey"],
    queryFn: UseQueryOptions["queryFn"],
    options: Omit<UseQueryOptions, "queryFn" | "queryKey"> = {},
  ) {
    return useQuery({
      queryKey,
      queryFn,
      retry: queryRetry,
      retryDelay,
      ...options,
    });
  }

  function mutate(
    mutationKey: UseMutationOptions["mutationKey"],
    mutationFn: UseMutationOptions["mutationFn"],
    options: Omit<UseMutationOptions, "mutationFn" | "mutationKey"> = {},
  ) {
    // Callers that set their own `retry` keep plain react-query semantics;
    // everyone else gets the in-band transient retry, which also honors the
    // server's Retry-After header.
    const useInBandRetry = options.retry === undefined && mutationFn != null;
    return useMutation({
      mutationKey,
      mutationFn: useInBandRetry
        ? withTransientErrorRetry(
            mutationFn,
            MAX_MUTATION_RETRIES,
            options.retryDelay,
          )
        : mutationFn,
      onSettled: (data, error, variables, onMutateResult, context) => {
        queryClient.invalidateQueries({ queryKey: mutationKey });
        options.onSettled?.(data, error, variables, onMutateResult, context);
      },
      ...options,
      retry: options.retry ?? false,
      retryDelay: options.retryDelay ?? retryDelay,
    });
  }

  return { query, mutate, queryClient };
}
