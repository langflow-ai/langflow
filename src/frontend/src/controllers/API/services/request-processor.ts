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

// 4xx responses are intentional client-side rejections (auth, validation,
// deployment guards, etc.) and won't change on retry.
function isClientError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false;
  const status = error.response?.status;
  return typeof status === "number" && status >= 400 && status < 500;
}

function makeRetry(maxRetries: number) {
  return (failureCount: number, error: unknown) => {
    if (isClientError(error)) return false;
    return failureCount < maxRetries;
  };
}

const queryRetry = makeRetry(5);
const mutationRetry = makeRetry(3);

const retryDelay = (attemptIndex: number) =>
  Math.min(1000 * 2 ** attemptIndex, 30000);

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
    return useMutation({
      mutationKey,
      mutationFn,
      onSettled: (data, error, variables, context) => {
        queryClient.invalidateQueries({ queryKey: mutationKey });
        options.onSettled && options.onSettled(data, error, variables, context);
      },
      ...options,
      retry: options.retry ?? mutationRetry,
      retryDelay: options.retryDelay ?? retryDelay,
    });
  }

  return { query, mutate, queryClient };
}
