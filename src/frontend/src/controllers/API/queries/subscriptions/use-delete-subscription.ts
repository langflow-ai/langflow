import { useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

interface DeleteSubscriptionVariables {
  subscriptionId: string;
}

export function useDeleteSubscription() {
  return useMutation({
    mutationFn: async (variables: DeleteSubscriptionVariables) => {
      const { subscriptionId } = variables;
      const response = await api.delete(
        `${getURL("SUBSCRIPTIONS")}/${subscriptionId}`,
      );
      return response.data;
    },
  });
}
