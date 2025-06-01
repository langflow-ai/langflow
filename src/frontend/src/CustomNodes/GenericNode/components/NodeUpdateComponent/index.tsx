import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";

export default function NodeUpdateComponent({
  hasBreakingChange,
  handleUpdateCode,
  loadingUpdate,
  isOutdated,
  openUpdateModal,
  setOpenUpdateModal,
}: {
  hasBreakingChange: boolean;
  handleUpdateCode: () => void;
  loadingUpdate: boolean;
  isOutdated: boolean;
  openUpdateModal: boolean;
  setOpenUpdateModal: (value: boolean) => void;
}) {
  return (
    <div
      className={cn(
        "flex w-full items-center gap-3 rounded-t-[0.69rem] border-b bg-muted p-2 px-4 py-2",
      )}
    >
      <div
        className={cn(
          "h-2.5 w-2.5 rounded-full",
          hasBreakingChange ? "bg-warning" : "bg-status-green",
        )}
      />
      <div className="mb-px flex-1 truncate text-mmd font-medium">
        {isOutdated &&
          (hasBreakingChange ? "Update available" : "Update ready")}
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 !text-mmd"
        onClick={(e) => {
          e.stopPropagation();
          setOpenUpdateModal(false);
        }}
        aria-label="Dismiss warning bar"
        data-testid="dismiss-warning-bar"
      >
        Dismiss
      </Button>
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
    </div>
  );
}
