import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";

interface RemovedReviewFlow {
  attachmentKey: string;
  flowName: string;
  versionLabel: string;
}

interface ReviewDetachingSectionProps {
  removedFlows: RemovedReviewFlow[];
}

export function ReviewDetachingSection({
  removedFlows,
}: ReviewDetachingSectionProps) {
  const { t } = useTranslation();
  if (removedFlows.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
      <div className="flex flex-col gap-3">
        <span className="text-sm font-medium text-destructive">
          {t("deployments.detaching")}
        </span>
        <div className="flex flex-col gap-2">
          {removedFlows.map((flow) => (
            <div
              key={flow.attachmentKey}
              className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-background p-3"
            >
              <ForwardedIconComponent
                name="Workflow"
                className="h-3.5 w-3.5 shrink-0 text-destructive/60"
              />
              <span className="text-sm text-foreground">{flow.flowName}</span>
              <Badge
                className="bg-accent-purple-muted text-accent-purple-muted-foreground"
                size="tag"
                variant="secondaryStatic"
              >
                {flow.versionLabel}
              </Badge>
              <Badge
                className="bg-destructive/10 text-destructive"
                size="tag"
                variant="secondaryStatic"
              >
                {t("deployments.removing")}
              </Badge>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {t("deployments.toolsWillBeDetached")}
        </p>
      </div>
    </div>
  );
}
