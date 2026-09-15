import { type RefObject, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useGetAuthorizationCapabilities } from "@/controllers/API/queries/authorization";
import { useGetShareSummary } from "@/controllers/API/queries/shares";
import type { ShareResourceType } from "@/types/authz";
import { ExistingAccessSection } from "./resource-share-dialog/existing-access-section";
import { ShareRecipientForm } from "./resource-share-dialog/share-recipient-form";

interface ResourceShareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  resourceType: ShareResourceType;
  resourceId: string;
  resourceName?: string;
  returnFocusRef?: RefObject<HTMLElement | null>;
}

const directGrantPageSize = 50;

export function ResourceShareDialog({
  open,
  onOpenChange,
  resourceType,
  resourceId,
  resourceName,
  returnFocusRef,
}: ResourceShareDialogProps) {
  const { t } = useTranslation();
  const [grantOffset, setGrantOffset] = useState(0);
  const capabilities = useGetAuthorizationCapabilities({ enabled: open });
  const summary = useGetShareSummary(
    {
      resourceType,
      resourceId,
      limit: directGrantPageSize,
      offset: grantOffset,
    },
    { enabled: open },
  );

  useEffect(() => {
    setGrantOffset(0);
  }, [open, resourceId, resourceType]);

  const contractReady = Boolean(
    !capabilities.isLoading &&
      !capabilities.isError &&
      capabilities.data?.enforcement_active &&
      capabilities.data.service_ready &&
      capabilities.data.user_team_sharing_supported &&
      capabilities.data.share_modes.includes("execute") &&
      capabilities.data.share_modes.includes("write"),
  );
  const canManage =
    contractReady &&
    !summary.isLoading &&
    !summary.isError &&
    summary.data?.can_manage_shares === true;
  const titleName =
    resourceName || summary.data?.display_name || t("sharing.resource.unnamed");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[88vh] max-w-2xl overflow-y-auto"
        data-testid="resource-share-dialog"
        onCloseAutoFocus={(event) => {
          const trigger = returnFocusRef?.current;
          if (trigger?.isConnected) {
            event.preventDefault();
            trigger.focus();
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>
            {t("sharing.dialog.title", { resourceName: titleName })}
          </DialogTitle>
          <DialogDescription>
            {t("sharing.dialog.description")}
          </DialogDescription>
        </DialogHeader>

        {resourceType === "project" && (
          <Alert>
            <AlertDescription>
              {t("sharing.project.inheritance")}
            </AlertDescription>
          </Alert>
        )}

        {(capabilities.isLoading || summary.isLoading) && (
          <div
            className="flex items-center gap-2 py-6 text-sm text-muted-foreground"
            role="status"
          >
            <ForwardedIconComponent name="Loader2" className="animate-spin" />
            {t("sharing.loading")}
          </div>
        )}

        {(capabilities.isError ||
          summary.isError ||
          (!capabilities.isLoading && !contractReady)) && (
          <Alert variant="destructive">
            <AlertDescription>{t("sharing.unavailable")}</AlertDescription>
          </Alert>
        )}

        {!summary.isLoading &&
          contractReady &&
          !summary.data?.can_manage_shares && (
            <Alert variant="destructive">
              <AlertDescription>{t("sharing.notAllowed")}</AlertDescription>
            </Alert>
          )}

        {canManage && summary.data && (
          <>
            <ShareRecipientForm
              open={open}
              resourceType={resourceType}
              resourceId={resourceId}
            />
            <ExistingAccessSection
              summary={summary.data}
              resourceType={resourceType}
              resourceId={resourceId}
              grantOffset={grantOffset}
              pageSize={directGrantPageSize}
              isFetching={summary.isFetching}
              onGrantOffsetChange={setGrantOffset}
            />
          </>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            {t("common.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default ResourceShareDialog;
