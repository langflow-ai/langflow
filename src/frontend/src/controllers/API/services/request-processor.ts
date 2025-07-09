import {
  type QueryClient,
  useMutation,
  type UseMutationOptions,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import type {
  MutationFunctionType,
  QueryFunctionType,
} from "../../../types/api";

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
      retry: 5,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
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
      retry: options.retry ?? 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    });
  }

  return { query, mutate, queryClient };
}
