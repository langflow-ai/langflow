import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

export default function NodeUpdateComponent({
  hasBreakingChange,
  blocked = false,
  showNode,
  handleUpdateCode,
  loadingUpdate,
  setDismissAll,
  dismissed = false,
  isRequired = false,
}: {
  hasBreakingChange: boolean;
  blocked?: boolean;
  showNode: boolean;
  handleUpdateCode: () => void;
  loadingUpdate: boolean;
  setDismissAll: (value: boolean) => void;
  dismissed?: boolean;
  isRequired?: boolean;
}) {
  const { t } = useTranslation();
  const showUpdateAction = !blocked;

  if (dismissed && isRequired) {
    return (
      <div
        className={cn(
          "flex w-full items-center gap-3 rounded-t-[0.69rem] border-b bg-muted p-2 px-4 py-2",
        )}
      >
        <div className={cn("h-2.5 w-2.5 rounded-full", "bg-accent-amber")} />
        <div className="mb-px flex-1 truncate text-mmd font-medium">
          {showNode &&
            (blocked
              ? t("node.updateBlockedMessage")
              : t("node.upgradeRequiredMessage"))}
        </div>
        {showUpdateAction && (
          <Button
            size="sm"
            className="!h-8 shrink-0 !text-mmd"
            onClick={(e) => {
              e.stopPropagation();
              handleUpdateCode();
            }}
            loading={loadingUpdate}
            data-testid={hasBreakingChange ? "review-button" : "update-button"}
          >
            {hasBreakingChange
              ? t("deployments.review")
              : t("nodeToolbar.update")}
          </Button>
        )}
      </div>
    );
  }

  const dotColor =
    blocked || isRequired
      ? "bg-accent-amber"
      : hasBreakingChange
        ? "bg-warning"
        : "bg-status-green";

  const label = blocked
    ? t("node.updateBlockedLabel")
    : isRequired
      ? t("node.updateRequiredLabel")
      : hasBreakingChange
        ? t("node.updateAvailableLabel")
        : t("node.updateReadyLabel");

  return (
    <div
      className={cn(
        "flex w-full items-center gap-3 rounded-t-[0.69rem] border-b bg-muted p-2 px-4 py-2",
      )}
    >
      <div className={cn("h-2.5 w-2.5 rounded-full", dotColor)} />
      <div className="mb-px flex-1 truncate text-mmd font-medium">
        {showNode && label}
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 !text-mmd"
        onClick={(e) => {
          e.stopPropagation();
          setDismissAll(true);
        }}
        aria-label={t("node.dismissWarning")}
        data-testid="dismiss-warning-bar"
      >
        {t("node.dismiss")}
      </Button>
      {showUpdateAction && (
        <Button
          size="sm"
          className="!h-8 shrink-0 !text-mmd"
          onClick={(e) => {
            e.stopPropagation();
            handleUpdateCode();
          }}
          loading={loadingUpdate}
          data-testid={hasBreakingChange ? "review-button" : "update-button"}
        >
          {hasBreakingChange
            ? t("deployments.review")
            : t("nodeToolbar.update")}
        </Button>
      )}
    </div>
  );
}
