import { Subscription } from "@/types/Subscription";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

interface GetSubscriptionsParams {
  skip?: number;
  limit?: number;
  refetchInterval?: number;
}

export function useGetSubscriptions(params: GetSubscriptionsParams = {}) {
  const { skip = 0, limit = 100, refetchInterval } = params;

  return useQuery({
    queryKey: ["subscriptions", { skip, limit }],
    queryFn: async () => {
      const response = await api.get<Subscription[]>(
        `${getURL("SUBSCRIPTIONS")}/`,
        {
          params: { skip, limit },
        },
      );
      return response.data;
    },
    refetchInterval: refetchInterval,
  });
}
