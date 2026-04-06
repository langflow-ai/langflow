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
              ? "Custom component cannot run while custom components are disabled"
              : "Upgrade is required to execute flow")}
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
            {hasBreakingChange ? "Review" : "Update"}
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
    ? "Custom component blocked"
    : isRequired
      ? "Update required"
      : hasBreakingChange
        ? "Update available"
        : "Update ready";

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
        aria-label="Dismiss warning bar"
        data-testid="dismiss-warning-bar"
      >
        Dismiss
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
          {hasBreakingChange ? "Review" : "Update"}
        </Button>
      )}
    </div>
  );
}
