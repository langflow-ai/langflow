import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { DeploymentType } from "@/pages/MainPage/pages/deploymentsPage/types";
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

  return (
    <>
      <DialogHeader>
        <DialogTitle>{t("deployments.reviewUpdate")}</DialogTitle>
        <DialogDescription>
          {t("deployments.reviewUpdateDescription")}
        </DialogDescription>
      </DialogHeader>

      <div className="flex flex-col gap-4">
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.12em] text-muted-foreground">
            <span>{deploymentTypeLabel}</span>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span>{t("deployments.deployment")}</span>
          </div>
          <div className="flex items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="truncate text-base font-semibold">
                {attachment.deployment_name}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2 text-sm">
              <span className="text-muted-foreground">
                {attachment.current_version_tag}
              </span>
              <ForwardedIconComponent
                name="ArrowRight"
                className="h-4 w-4 text-muted-foreground"
              />
              <Badge variant="default">{newVersionTag}</Badge>
            </div>
          </div>
        </div>

        {hasManyAttachments && (
          <div className="space-y-2">
            <div>
              <p className="text-sm font-medium">
                {t("deployments.chooseDeployedVersion")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("deployments.selectDeployedToolToReplace")}
              </p>
            </div>
            <RadioGroup
              value={attachment.provider_snapshot_id}
              onValueChange={onSelectAttachment}
              className="gap-2"
            >
              {attachments.map((item) => {
                const isSelected =
                  attachment.provider_snapshot_id === item.provider_snapshot_id;

                return (
                  <div
                    key={item.provider_snapshot_id}
                    className={`rounded-lg border px-3 py-2 transition-colors ${
                      isSelected
                        ? "border-primary/40 bg-primary/5"
                        : "border-border/60 hover:border-border hover:bg-muted/20"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <RadioGroupItem
                        value={item.provider_snapshot_id}
                        id={`attachment-${item.provider_snapshot_id}`}
                      />
                      <Label
                        htmlFor={`attachment-${item.provider_snapshot_id}`}
                        className="flex flex-1 cursor-pointer items-center justify-between gap-3"
                      >
                        <div className="min-w-0">
                          <span className="block truncate text-sm font-medium">
                            {item.tool_name}
                          </span>
                          {isSelected && (
                            <span className="block text-xs text-muted-foreground">
                              {t("deployments.willBeReplaced")}
                            </span>
                          )}
                        </div>
                        <Badge variant="secondary">
                          {item.current_version_tag}
                        </Badge>
                      </Label>
                    </div>
                  </div>
                );
              })}
            </RadioGroup>
          </div>
        )}

        {!hasManyAttachments && (
          <div className="rounded-lg border border-border/60 bg-muted/10 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {attachment.tool_name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("deployments.willBeReplaced")}
                </p>
              </div>
              <Badge variant="secondary">
                {attachment.current_version_tag}
              </Badge>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-4">
        <Button variant="ghost" onClick={onCancel} disabled={isBusy}>
          {t("deployments.cancel")}
        </Button>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={onBack} disabled={isBusy}>
            {t("deployments.back")}
          </Button>
          <Button onClick={onConfirm} disabled={isBusy}>
            {t("deployments.update")}
          </Button>
        </div>
      </div>
    </>
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
