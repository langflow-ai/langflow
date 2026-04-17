import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { DeploymentType } from "../types";
import type { ReviewFlowItem } from "./step-review-types";

interface StepReviewSummaryCardProps {
  deploymentType: DeploymentType;
  deploymentName: string;
  selectedLlm: string;
  reviewFlows: ReviewFlowItem[];
}

export function StepReviewSummaryCard({
  deploymentType,
  deploymentName,
  selectedLlm,
  reviewFlows,
}: StepReviewSummaryCardProps) {
  return (
    <div className="rounded-xl border border-border bg-background p-4">
      <div className="grid grid-cols-2 gap-6">
        <div className="flex flex-col gap-3">
          <span className="text-sm font-medium text-foreground">
            Deployment
          </span>
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="w-10 text-xs text-muted-foreground">Type</span>
              <div className="flex items-center gap-1.5">
                <ForwardedIconComponent
                  name={deploymentType === "agent" ? "Bot" : "Server"}
                  className="h-3.5 w-3.5 text-muted-foreground"
                />
                <span className="text-sm capitalize text-foreground">
                  {deploymentType}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-10 text-xs text-muted-foreground">Name</span>
              <span className="text-sm text-foreground">
                {deploymentName || "—"}
              </span>
            </div>
            {selectedLlm && (
              <div className="flex items-center gap-2">
                <span className="w-10 text-xs text-muted-foreground">
                  Model
                </span>
                <span className="text-sm text-foreground">{selectedLlm}</span>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <span className="text-sm font-medium text-foreground">
            Attached Flows
          </span>
          <div className="flex flex-col gap-1.5">
            {reviewFlows.length === 0 ? (
              <span className="text-sm text-muted-foreground">—</span>
            ) : (
              reviewFlows.map((item) => (
                <div key={item.flowId} className="flex items-center gap-1.5">
                  <ForwardedIconComponent
                    name="Workflow"
                    className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                  />
                  <span className="text-sm text-foreground">
                    {item.flowName}
                  </span>
                  <Badge
                    variant="secondaryStatic"
                    size="tag"
                    className="bg-accent-purple-muted text-accent-purple-muted-foreground"
                  >
                    {item.versionLabel}
                  </Badge>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
