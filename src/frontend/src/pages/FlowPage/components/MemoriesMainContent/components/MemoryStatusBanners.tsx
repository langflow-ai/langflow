import IconComponent from "@/components/common/genericIconComponent";
import type { MemoryStatusBannersProps } from "../types";

export function MemoryStatusBanners({
  memory,
  isProcessing,
}: MemoryStatusBannersProps) {
  return (
    <>
      {isProcessing && (
        <div className="mb-4 rounded-lg border border-primary/20 bg-primary/5 p-4">
          <div className="flex items-center gap-3">
            <IconComponent
              name="Loader2"
              className="h-5 w-5 animate-spin text-primary"
            />
            <div>
              <p className="text-sm font-medium">
                {memory.status === "generating"
                  ? "Generating memory..."
                  : "Updating memory..."}
              </p>
              <p className="text-xs text-muted-foreground">
                {memory.total_messages_processed} message(s) processed
              </p>
            </div>
          </div>
        </div>
      )}

      {memory.status === "failed" && memory.error_message && (
        <div className="mb-4 rounded-lg border border-destructive/20 bg-destructive/5 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <IconComponent
                name="AlertTriangle"
                className="mt-0.5 h-5 w-5 text-destructive"
              />
              <div>
                <p className="text-sm font-medium text-destructive">
                  Update Failed
                </p>
                <p className="mt-1 text-xs text-destructive/80">
                  {memory.error_message}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
