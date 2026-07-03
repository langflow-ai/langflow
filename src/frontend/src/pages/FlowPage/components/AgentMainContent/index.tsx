import { useGetA2ACard } from "@/controllers/API/queries/a2a/use-get-a2a-card";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import AgentCardPanel from "./components/AgentCardPanel";
import AgentTestConversation from "./components/AgentTestConversation";
import { cardRequiresApiKey } from "./types";

export default function AgentMainContent() {
  // Gate and publish on the SAVED flow: the live A2A endpoint only serves the
  // persisted a2a_enabled, not the in-canvas edit state.
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  // Server-wide LANGFLOW_A2A_ENABLED. When off the whole A2A surface 404s.
  const serverEnabled = useUtilityStore((state) => state.a2aEnabled);

  const flowId = currentFlow?.id ?? "";
  const isPublished = !!currentFlow?.a2a_enabled;

  // The resolved card only exists once published; fetch it to preview the input
  // contract + exposure line callers actually see. Draft has no card to show.
  const cardQuery = useGetA2ACard(
    { flowId },
    { enabled: !!flowId && isPublished && serverEnabled, retry: false },
  );
  const card = cardQuery.data ?? null;

  return (
    <div className="flex h-full w-full flex-col overflow-hidden lg:flex-row">
      <div className="flex w-full flex-col overflow-y-auto border-b p-6 lg:max-w-md lg:border-b-0 lg:border-r">
        <AgentCardPanel
          currentFlow={currentFlow}
          serverEnabled={serverEnabled}
          card={card}
          cardLoading={cardQuery.isFetching}
        />
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <AgentTestConversation
          flowId={flowId}
          isPublished={isPublished}
          serverEnabled={serverEnabled}
          requiresApiKey={cardRequiresApiKey(card)}
        />
      </div>
    </div>
  );
}
