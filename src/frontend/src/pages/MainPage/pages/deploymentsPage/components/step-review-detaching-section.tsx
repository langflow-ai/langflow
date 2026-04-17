import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { RemovedReviewFlowItem } from "./step-review-types";

interface StepReviewDetachingSectionProps {
  removedFlows: RemovedReviewFlowItem[];
}

export function StepReviewDetachingSection({
  removedFlows,
}: StepReviewDetachingSectionProps) {
  if (removedFlows.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
      <div className="flex flex-col gap-3">
        <span className="text-sm font-medium text-destructive">Detaching</span>
        <div className="flex flex-col gap-2">
          {removedFlows.map((flow) => (
            <div
              key={flow.flowId}
              className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-background p-3"
            >
              <ForwardedIconComponent
                name="Workflow"
                className="h-3.5 w-3.5 shrink-0 text-destructive/60"
              />
              <span className="text-sm text-foreground">{flow.flowName}</span>
              <Badge
                variant="secondaryStatic"
                size="tag"
                className="bg-destructive/10 text-destructive"
              >
                removing
              </Badge>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          These tools will be detached from the agent. They will remain
          available on your provider tenant.
        </p>
      </div>
    </div>
  );
}
