import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

export default function NodeUpdateComponent({
  hasBreakingChange,
  blocked = false,
  blockedByCatalogPolicy = false,
  showNode,
  handleUpdateCode,
  loadingUpdate,
  setDismissAll,
  dismissed = false,
  isRequired = false,
  disabled = false,
}: {
  hasBreakingChange: boolean;
  blocked?: boolean;
  blockedByCatalogPolicy?: boolean;
  showNode: boolean;
  handleUpdateCode: () => void;
  loadingUpdate: boolean;
  setDismissAll: (value: boolean) => void;
  dismissed?: boolean;
  isRequired?: boolean;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const showUpdateAction = !blocked;
  // `blocked` only reaches here when a catalog policy applies or custom
  // components are off, so those are the only two causes the copy can name.
  const blockedMessage = blockedByCatalogPolicy
    ? t("node.updateBlockedByPolicyMessage")
    : t("node.updateBlockedMessage");
  const blockedLabel = blockedByCatalogPolicy
    ? t("node.updateBlockedByPolicyLabel")
    : t("node.updateBlockedLabel");

  if (blockedByCatalogPolicy) {
    return (
      <div
        className="flex w-full items-start gap-3 rounded-t-[0.69rem] border-b bg-muted px-4 py-2"
        role="status"
        aria-live="polite"
      >
        <div className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-accent-amber" />
        <div className="min-w-0 flex-1">
          <p className="text-mmd font-medium">{blockedLabel}</p>
          <p
            className={cn(
              "mt-0.5 text-xs leading-4 text-muted-foreground",
              !showNode && "sr-only",
            )}
          >
            {blockedMessage}
          </p>
        </div>
      </div>
    );
  }

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
            (blocked ? blockedMessage : t("node.upgradeRequiredMessage"))}
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
            disabled={disabled}
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
    ? blockedLabel
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
      {/* A blocked node offers no update action, so the label is the only
          explanation it has. Keep it even while collapsed, where the row is
          narrow enough to truncate, and carry the full text in the title. */}
      <div
        className="mb-px flex-1 truncate text-mmd font-medium"
        title={blocked ? blockedMessage : undefined}
      >
        {showNode || blocked ? label : null}
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
        disabled={disabled}
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
          disabled={disabled}
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
