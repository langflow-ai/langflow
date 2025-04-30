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
        "flex h-10 w-full items-center gap-4 rounded-t-[0.69rem] p-2 px-4",
        hasBreakingChange
          ? "bg-destructive text-destructive-foreground"
          : "bg-warning text-warning-foreground",
      )}
    >
      <ForwardedIconComponent
        name="AlertTriangle"
        strokeWidth={ICON_STROKE_WIDTH}
        className="icon-size shrink-0"
      />
      <span className="flex-1 truncate text-sm font-medium">
        {showNode && (hasBreakingChange ? "Breaking Change" : "Update Ready")}
      </span>

      <Button
        variant={hasBreakingChange ? "destructive" : "warning"}
        size="iconMd"
        className="shrink-0 px-2.5 text-xs"
        onClick={handleUpdateCode}
        loading={loadingUpdate}
        data-testid="update-button"
      >
        Update
      </Button>
      <Button
        variant="ghost"
        size="iconSm"
        className="ml-2 shrink-0 px-2.5 text-xs"
        onClick={() => setDismissAll(true)}
        aria-label="Dismiss warning bar"
        data-testid="dismiss-warning-bar"
      >
        <ForwardedIconComponent
          name="X"
          strokeWidth={ICON_STROKE_WIDTH}
          className="icon-size"
        />
      </Button>
    </div>
  );
}
