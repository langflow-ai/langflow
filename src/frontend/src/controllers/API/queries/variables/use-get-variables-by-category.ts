import { useQuery } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export function useGetVariablesByCategory(category: string) {
  const {
    data: variables,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["variables", "category", category],
    queryFn: async () => {
      const response = await api.get(
        `${getURL("VARIABLES")}/category/${category}`,
      );
      return response.data;
    },
    retry: false,
  });

  return {
    variables,
    isLoading,
    isError,
    error: error as AxiosError,
    refetch,
  };
}
