import { useMemo } from "react";
import { useGetA2ACard } from "@/controllers/API/queries/a2a/use-get-a2a-card";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { NodeDataType } from "@/types/flow";
import AgentCardPanel from "./components/AgentCardPanel";
import AgentTestConversation from "./components/AgentTestConversation";
import { cardRequiresApiKey } from "./types";

// A2A can drive a flow only if a message can enter (ChatInput, or a HumanInput
// pause that turn-2 text resumes) and a reply can leave (ChatOutput). This
// mirrors what the langflow A2A server actually runs, so the toggle is only
// live when the flow can genuinely serve. Read from the live canvas so the
// guidance updates as the user edits, before any save.
function a2aEligibility(nodes: { data?: unknown }[]) {
  let hasInput = false;
  let hasOutput = false;
  for (const node of nodes) {
    const type = (node.data as NodeDataType | undefined)?.type;
    if (type === "ChatInput" || type === "HumanInput") hasInput = true;
    if (type === "ChatOutput") hasOutput = true;
  }
  return { eligible: hasInput && hasOutput, hasInput, hasOutput };
}

export default function AgentMainContent() {
  // Gate and publish on the SAVED flow: the live A2A endpoint only serves the
  // persisted a2a_enabled, not the in-canvas edit state.
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  // Server-wide LANGFLOW_A2A_ENABLED. When off the whole A2A surface 404s.
  const serverEnabled = useUtilityStore((state) => state.a2aEnabled);
  const nodes = useFlowStore((state) => state.nodes);
  const eligibility = useMemo(() => a2aEligibility(nodes), [nodes]);

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
          eligible={eligibility.eligible}
          hasInput={eligibility.hasInput}
          hasOutput={eligibility.hasOutput}
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
