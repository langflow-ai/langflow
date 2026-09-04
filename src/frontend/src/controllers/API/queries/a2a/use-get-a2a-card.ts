import type { A2AAgentCard } from "@/pages/FlowPage/components/AgentMainContent/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetA2ACard {
  flowId: string;
}

// Fetches the resolved A2A agent card from the public .well-known endpoint. Only
// serves once the flow is saved with a2a_enabled true (else 404), so callers gate
// `enabled` on the saved publish flag — the draft state has no card to show.
export const useGetA2ACard: useQueryFunctionType<IGetA2ACard, A2AAgentCard> = (
  params,
  options,
) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    const { data } = await api.get<A2AAgentCard>(
      `${getURL("A2A")}/${params.flowId}/.well-known/agent-card.json`,
    );
    return data;
  };

  return query(["useGetA2ACard", params.flowId], responseFn, { ...options });
};
