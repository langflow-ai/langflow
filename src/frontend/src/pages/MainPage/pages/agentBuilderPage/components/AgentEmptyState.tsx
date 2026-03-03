import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

interface AgentEmptyStateProps {
  onCreateAgent: () => void;
}

export function AgentEmptyState({ onCreateAgent }: AgentEmptyStateProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-muted-foreground">
      <ForwardedIconComponent name="Bot" className="h-12 w-12 opacity-30" />
      <div className="text-center">
        <p className="text-lg font-medium">No agents yet</p>
        <p className="mt-1 text-sm">
          Create an agent to start chatting with AI using tools.
        </p>
      </div>
      <Button onClick={onCreateAgent} variant="default" size="sm">
        <ForwardedIconComponent name="Plus" className="mr-2 h-4 w-4" />
        Create Agent
      </Button>
    </div>
  );
}
