import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type { AgentRead } from "@/controllers/API/queries/agents";
import { AgentCard } from "./AgentCard";

interface AgentListProps {
  agents: AgentRead[];
  selectedAgentId: string | null;
  onSelectAgent: (agent: AgentRead) => void;
  onCreateAgent: () => void;
  isLoading: boolean;
}

export function AgentList({
  agents,
  selectedAgentId,
  onSelectAgent,
  onCreateAgent,
  isLoading,
}: AgentListProps) {
  return (
    <div className="flex h-full w-80 flex-col border-r">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-sm font-semibold">Agents</h2>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onCreateAgent}
          data-testid="create-agent-button"
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-3">
        {isLoading && (
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            Loading...
          </div>
        )}
        {!isLoading && agents.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center text-sm text-muted-foreground">
            <p>No agents created yet.</p>
            <Button
              variant="link"
              size="sm"
              className="mt-1"
              onClick={onCreateAgent}
            >
              Create your first agent
            </Button>
          </div>
        )}
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            isSelected={agent.id === selectedAgentId}
            onSelect={onSelectAgent}
          />
        ))}
      </div>
    </div>
  );
}
