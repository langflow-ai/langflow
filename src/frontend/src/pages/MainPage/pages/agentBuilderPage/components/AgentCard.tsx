import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { AgentRead } from "@/controllers/API/queries/agents";
import { cn } from "@/utils/utils";

interface AgentCardProps {
  agent: AgentRead;
  isSelected: boolean;
  onSelect: (agent: AgentRead) => void;
}

export function AgentCard({ agent, isSelected, onSelect }: AgentCardProps) {
  const toolCount = agent.tool_components.length;

  return (
    <button
      type="button"
      onClick={() => onSelect(agent)}
      className={cn(
        "flex w-full flex-col gap-1 rounded-lg border p-3 text-left transition-colors",
        "hover:bg-accent",
        isSelected && "border-primary bg-accent",
      )}
      data-testid={`agent-card-${agent.id}`}
    >
      <div className="flex items-center gap-2">
        <ForwardedIconComponent
          name={agent.icon || "Bot"}
          className="h-4 w-4 shrink-0"
        />
        <span className="truncate text-sm font-medium">{agent.name}</span>
      </div>
      {agent.description && (
        <p className="truncate text-xs text-muted-foreground">
          {agent.description}
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        {toolCount} {toolCount === 1 ? "tool" : "tools"}
      </p>
    </button>
  );
}
