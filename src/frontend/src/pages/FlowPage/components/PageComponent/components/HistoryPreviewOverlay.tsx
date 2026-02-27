import ForwardedIconComponent from "@/components/common/genericIconComponent";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useHistoryPreviewStore from "@/stores/historyPreviewStore";
import { CanvasBadge } from "./CanvasBanner";
import RestoreVersionButton from "./RestoreVersionButton";
import SaveSnapshotButton from "./SaveSnapshotButton";

export default function HistoryPreviewOverlay() {
  const previewLabel = useHistoryPreviewStore((s) => s.previewLabel);
  const previewId = useHistoryPreviewStore((s) => s.previewId);
  const isPreviewLoading = useHistoryPreviewStore((s) => s.isPreviewLoading);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  if (previewLabel === null) return null;

  return (
    <div className="history-preview-overlay pointer-events-none absolute inset-0 z-50">
      <CanvasBadge>
        <span className="h-2 w-2 shrink-0 rounded-lg bg-[#6366F1]" />
        <span className="text-sm">
          {previewLabel === "Current Draft"
            ? "Current Flow"
            : `Previewing ${previewLabel}`}
        </span>
        <span className="text-muted-foreground text-sm">(Read-Only)</span>
      </CanvasBadge>

      {isPreviewLoading && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="pointer-events-auto flex items-center gap-2 rounded-lg border bg-background px-4 py-2 shadow-lg">
            <ForwardedIconComponent
              name="Loader2"
              className="h-4 w-4 animate-spin text-muted-foreground"
            />
            <span className="text-sm text-muted-foreground">
              Loading preview...
            </span>
          </div>
        </div>
      )}

      {previewLabel === "Current Draft" && (
        <SaveSnapshotButton flowId={currentFlowId} />
      )}

      {previewId && previewLabel && previewLabel !== "Current Draft" && (
        <RestoreVersionButton
          flowId={currentFlowId}
          historyId={previewId}
          versionTag={previewLabel}
        />
      )}
    </div>
  );
}
