import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";

interface ReviewDetachingSectionProps {
  allFlows: Array<{ id: string; name: string }>;
  removedFlowIds: Set<string>;
}

export function ReviewDetachingSection({
  allFlows,
  removedFlowIds,
}: ReviewDetachingSectionProps) {
  if (removedFlowIds.size === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
      <div className="flex flex-col gap-3">
        <span className="text-sm font-medium text-destructive">Detaching</span>
        <div className="flex flex-col gap-2">
          {Array.from(removedFlowIds).map((flowId) => {
            const flow = allFlows.find((item) => item.id === flowId);

            return (
              <div
                key={flowId}
                className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-background p-3"
              >
                <ForwardedIconComponent
                  name="Workflow"
                  className="h-3.5 w-3.5 shrink-0 text-destructive/60"
                />
                <span className="text-sm text-foreground">
                  {flow?.name ?? "Unknown flow"}
                </span>
                <Badge
                  className="bg-destructive/10 text-destructive"
                  size="tag"
                  variant="secondaryStatic"
                >
                  removing
                </Badge>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground">
          These tools will be detached from the agent. They will remain
          available on your provider tenant.
        </p>
      </div>
    </div>
  );
}
