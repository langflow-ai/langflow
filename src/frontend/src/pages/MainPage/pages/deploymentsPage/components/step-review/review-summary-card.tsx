import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { DeploymentType } from "../../types";
import type { ReviewFlowItem } from "./types";

interface ReviewSummaryCardProps {
  deploymentName: string;
  deploymentType: DeploymentType;
  reviewFlows: ReviewFlowItem[];
  selectedLlm: string;
}

export function ReviewSummaryCard({
  deploymentName,
  deploymentType,
  reviewFlows,
  selectedLlm,
}: ReviewSummaryCardProps) {
  const { t } = useTranslation();
  return (
    <div className="rounded-xl border border-border bg-background p-4">
      <div className="grid grid-cols-2 gap-6">
        <div className="flex flex-col gap-3">
          <span className="text-sm font-medium text-foreground">
            {t("deployments.deploymentLabel")}
          </span>
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="w-24 text-xs text-muted-foreground">
                {t("deployments.labelType")}
              </span>
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
              <span className="w-24 text-xs text-muted-foreground">
                {t("deployments.labelName")}
              </span>
              <span className="text-sm text-foreground">
                {deploymentName || "—"}
              </span>
            </div>
            {selectedLlm && (
              <div className="flex items-center gap-2">
                <span className="w-24 text-xs text-muted-foreground">
                  {t("deployments.labelModel")}
                </span>
                <span className="text-sm text-foreground">{selectedLlm}</span>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <span className="text-sm font-medium text-foreground">
            {t("deployments.attachedFlowsLabel")}
          </span>
          <div className="flex flex-col gap-1.5">
            {reviewFlows.length === 0 ? (
              <span className="text-sm text-muted-foreground">—</span>
            ) : (
              reviewFlows.map((item) => (
                <div
                  key={item.attachmentKey}
                  className="flex items-center gap-1.5"
                >
                  <ForwardedIconComponent
                    name="Workflow"
                    className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                  />
                  <span className="text-sm text-foreground">
                    {item.flowName}
                  </span>
                  <Badge
                    className="bg-accent-purple-muted text-accent-purple-muted-foreground"
                    size="tag"
                    variant="secondaryStatic"
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
