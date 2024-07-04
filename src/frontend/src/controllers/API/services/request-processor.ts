import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MutationFunctionType, QueryFunctionType } from "../../../types/api";

export function UseRequestProcessor(): {
  query: QueryFunctionType;
  mutate: MutationFunctionType;
} {
  const queryClient = useQueryClient();

  function query(queryKey, queryFn, options = {}) {
    return useQuery({
      queryKey,
      queryFn,
      ...options,
    });
  }

  function mutate(mutationKey, mutationFn, options = {}) {
    return useMutation({
      mutationKey,
      mutationFn,
      onSettled: () => queryClient.invalidateQueries(mutationKey),
      ...options,
    });
  }

  return { query, mutate };
}
