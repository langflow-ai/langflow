import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useVersionPreviewStore from "@/stores/historyPreviewStore";
import RestoreVersionButton from "./RestoreVersionButton";
import SaveSnapshotButton from "./SaveSnapshotButton";

export default function VersionPreviewOverlay() {
  const previewLabel = useVersionPreviewStore((s) => s.previewLabel);
  const previewId = useVersionPreviewStore((s) => s.previewId);
  const isPreviewLoading = useVersionPreviewStore((s) => s.isPreviewLoading);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  if (previewLabel === null) return null;

  return (
    <div className="version-preview-overlay pointer-events-none absolute inset-0 z-50">
      <Badge
        variant="outline"
        className="pointer-events-auto absolute left-4 top-4 h-8 whitespace-nowrap rounded-lg border-accent-indigo-foreground px-3 text-xs font-medium text-accent-indigo-foreground shadow-md backdrop-blur-sm"
      >
        <span className="text-sm">
          {previewLabel === "Current Draft" ? (
            <div className="flex items-center gap-2">
              Current Flow{" "}
              <span className="font-mono text-xs opacity-80">(Read-Only)</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              Previewing {previewLabel}{" "}
              <span className="font-mono text-xs opacity-80">(Read-Only)</span>
            </div>
          )}
        </span>
      </Badge>

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
          versionId={previewId}
          versionTag={previewLabel}
        />
      )}
    </div>
  );
}
