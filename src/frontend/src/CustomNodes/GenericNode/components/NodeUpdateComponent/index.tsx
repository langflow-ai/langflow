import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";

export default function NodeUpdateComponent({
  hasBreakingChange,
  showNode,
  handleUpdateCode,
  loadingUpdate,
  setDismissAll,
}: {
  hasBreakingChange: boolean;
  showNode: boolean;
  handleUpdateCode: () => void;
  loadingUpdate: boolean;
  setDismissAll: (value: boolean) => void;
}) {
  return (
    <div
      className={cn(
        "bg-muted flex w-full items-center gap-3 rounded-t-[0.69rem] border-b p-2 px-4 py-2",
      )}
    >
      <div
        className={cn(
          "h-2.5 w-2.5 rounded-full",
          hasBreakingChange ? "bg-warning" : "bg-status-green",
        )}
      />
      <div className="text-mmd mb-px flex-1 truncate font-medium">
        {showNode && (hasBreakingChange ? "Update available" : "Update ready")}
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="text-mmd! shrink-0"
        onClick={(e) => {
          e.stopPropagation();
          setDismissAll(true);
        }}
        aria-label="Dismiss warning bar"
        data-testid="dismiss-warning-bar"
      >
        Dismiss
      </Button>
      <Button
        size="sm"
        className="text-mmd! h-8! shrink-0"
        onClick={(e) => {
          e.stopPropagation();
          handleUpdateCode();
        }}
        loading={loadingUpdate}
        data-testid={hasBreakingChange ? "review-button" : "update-button"}
      >
        {hasBreakingChange ? "Review" : "Update"}
      </Button>
    </div>
  );
}
