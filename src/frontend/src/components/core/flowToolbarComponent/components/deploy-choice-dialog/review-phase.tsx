import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RadioSelectItem } from "@/pages/MainPage/pages/deploymentsPage/components/radio-select-item";
import type { DeploymentType } from "@/pages/MainPage/pages/deploymentsPage/types";
import { cn } from "@/utils/utils";
import ReviewPhaseSkeletonContent from "./review-phase-skeleton";
import type { FlowAttachment } from "./types";

interface ReviewPhaseContentProps {
  attachments: FlowAttachment[];
  attachment: FlowAttachment | null;
  loading?: boolean;
  onSelectAttachment: (providerSnapshotId: string) => void;
  newVersionTag: string;
  isBusy: boolean;
  onBack: () => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ReviewPhaseContent({
  attachments,
  attachment,
  loading = false,
  onSelectAttachment,
  newVersionTag,
  isBusy,
  onBack,
  onConfirm,
  onCancel,
}: ReviewPhaseContentProps) {
  const { t } = useTranslation();

  if (loading || !attachment) {
    return <ReviewPhaseSkeletonContent />;
  }

  const hasManyAttachments = attachments.length > 1;
  const deploymentTypeLabel = getDeploymentTypeLabel(
    attachment.deployment_type,
    t,
  );
  const currentVersionTag = attachment.current_version_tag;
  const replaceActionLabel = t("deployments.replaceVersionWithVersion", {
    current: currentVersionTag,
    next: newVersionTag,
  });

  return (
    <>
      <DialogHeader className="gap-2">
        <DialogTitle className="text-xl font-semibold">
          {t("deployments.updateDeployment")}
        </DialogTitle>
        <DialogDescription className="text-sm leading-5">
          {t("deployments.updateDeploymentDescription")}
        </DialogDescription>
      </DialogHeader>

      <div className="flex flex-col gap-6">
        <div className="space-y-4">
          <div className="text-xxs font-semibold uppercase tracking-wider text-muted-foreground/70">
            {deploymentTypeLabel} {t("deployments.deployment")}:{" "}
            <span>{attachment.deployment_name}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <VersionSummaryCard
                label={t("deployments.selectedTarget")}
                value={currentVersionTag}
              />
            </div>
            <ForwardedIconComponent
              name="ArrowRight"
              className="h-5 w-5 text-muted-foreground"
            />
            <div className="min-w-0 flex-1">
              <VersionSummaryCard
                label={t("deployments.flowVersion")}
                value={newVersionTag}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-lg border border-deployment-callout-border bg-deployment-callout px-4 py-3 text-deployment-callout-foreground">
          <ForwardedIconComponent name="Info" className="h-5 w-5 shrink-0" />
          <p className="text-sm leading-5">
            {t("deployments.replaceVersionNotice", {
              current: currentVersionTag,
              next: newVersionTag,
            })}
          </p>
        </div>

        <div className="space-y-3">
          <div className="space-y-2">
            <h3 className="text-base font-semibold">
              {t("deployments.selectVersionToReplace")}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t("deployments.selectedDeployedVersionWillUpdate", {
                next: newVersionTag,
              })}
            </p>
          </div>

          <div className="grid gap-2">
            {attachments.map((item) => {
              const isSelected =
                attachment.provider_snapshot_id === item.provider_snapshot_id;

              return (
                <RadioSelectItem
                  key={item.provider_snapshot_id}
                  name="deployment-attachment"
                  value={item.provider_snapshot_id}
                  selected={isSelected}
                  onChange={() => onSelectAttachment(item.provider_snapshot_id)}
                  className={cn(
                    "min-h-16 rounded-lg px-4 py-3",
                    isSelected
                      ? "border-border bg-muted"
                      : "border-muted hover:border-border hover:bg-muted/40",
                  )}
                  indicatorClassName={cn(
                    "h-4 w-4",
                    isSelected
                      ? "border-primary bg-primary"
                      : "border-border bg-muted",
                  )}
                  dotClassName="h-2 w-2 bg-background"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">
                      {item.tool_name}
                    </div>
                    <div className="truncate text-xs font-medium text-muted-foreground/70">
                      {isSelected ? (
                        <>
                          {t("deployments.currentDeploymentTarget")}{" "}
                          <span className="text-muted-foreground/70">•</span>{" "}
                          <span className="font-medium text-accent-amber-foreground">
                            {t("deployments.willBeReplacedByVersion", {
                              next: newVersionTag,
                            })}
                          </span>
                        </>
                      ) : (
                        t("deployments.deployedVersion")
                      )}
                    </div>
                  </div>
                  <span className="shrink-0 text-sm font-semibold text-muted-foreground">
                    {item.current_version_tag}
                  </span>
                </RadioSelectItem>
              );
            })}
          </div>

          {!hasManyAttachments && (
            <p className="sr-only">{t("deployments.singleAttachmentTarget")}</p>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between pt-3">
        <Button variant="ghost" onClick={onCancel} disabled={isBusy}>
          {t("deployments.cancel")}
        </Button>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={onBack} disabled={isBusy}>
            {t("deployments.back")}
          </Button>
          <Button onClick={onConfirm} disabled={isBusy} ignoreTitleCase>
            {replaceActionLabel}
          </Button>
        </div>
      </div>
    </>
  );
}

function VersionSummaryCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex h-16 items-center justify-center rounded-lg bg-muted px-4">
      <div className="space-y-2 text-center">
        <div className="text-xxs font-semibold uppercase tracking-wider text-muted-foreground/70">
          {label}
        </div>
        <div className="text-sm font-semibold">{value}</div>
      </div>
    </div>
  );
}

function getDeploymentTypeLabel(
  deploymentType: DeploymentType,
  t: (key: string) => string,
) {
  if (deploymentType === "agent") {
    return t("deployments.agentTypeLabel");
  }

  if (deploymentType === "mcp") {
    return t("deployments.mcpTypeLabel");
  }

  return deploymentType;
}
