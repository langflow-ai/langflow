import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useFlowNames, usePreviewChanges } from "@/hooks/use-history-changes";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useRevisionPlaybackStore from "@/stores/revisionPlaybackStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";
import { revisionOfSelection } from "../../flowSidebarComponent/components/FlowVersionSidebar/constants";
import { CanvasBadge } from "./CanvasBanner";
import HistorySlider from "./HistorySlider";
import RestoreRevisionButton from "./RestoreRevisionButton";
import RestoreVersionButton from "./RestoreVersionButton";
import SaveSnapshotButton from "./SaveSnapshotButton";

// Removals listed in the badge before the rest are counted.
const MAX_REMOVALS_SHOWN = 3;

export default function VersionPreviewOverlay() {
  const previewLabel = useVersionPreviewStore((s) => s.previewLabel);
  const previewId = useVersionPreviewStore((s) => s.previewId);
  const previewDescription = useVersionPreviewStore(
    (s) => s.previewDescription,
  );
  const isPreviewLoading = useVersionPreviewStore((s) => s.isPreviewLoading);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const timeline = useRevisionPlaybackStore((s) => s.timeline);
  const changes = usePreviewChanges();
  const names = useFlowNames();

  const { t } = useTranslation();

  if (previewLabel === null) return null;
  // What was removed here is not on the canvas to highlight, so it is named.
  const authorOf = (actor: { username: string | null }) =>
    actor.username ?? t("flowHistory.unknownAuthor");
  const removals = [
    ...(changes?.removedNodes ?? []).map((node) =>
      t("flowHistory.highlight.byAuthor", {
        change: t("flowHistory.op.deletedNode", { name: names.node(node.id) }),
        author: authorOf(node.actor),
      }),
    ),
    ...(changes?.removedEdges ?? []).map((edge) =>
      t("flowHistory.highlight.byAuthor", {
        change:
          edge.source && edge.target
            ? t("flowHistory.op.disconnected", {
                source: names.node(edge.source),
                target: names.node(edge.target),
              })
            : t("flowHistory.op.removedConnection"),
        author: authorOf(edge.actor),
      }),
    ),
  ];
  const previewRevision = revisionOfSelection(previewId);
  // Restore returns to the end of an entry, a state someone actually saved;
  // the points inside an entry are only shown.
  const restorable =
    previewRevision !== null &&
    (!timeline ||
      timeline.entries.some((entry) => entry.end_revision === previewRevision));

  return (
    <div className="version-preview-overlay pointer-events-none absolute inset-0 z-50">
      <CanvasBadge className="flex-col items-start whitespace-normal">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 shrink-0 rounded-lg bg-[#6366F1]" />
          <span className="text-sm">
            {previewLabel === "Current Draft"
              ? t("version.currentFlow")
              : t("version.previewing", { label: previewLabel })}
          </span>
          <span className="text-muted-foreground text-sm">
            {t("version.readOnly")}
          </span>
        </div>
        {previewDescription && (
          <span className="max-w-[300px] pl-4 text-xs text-muted-foreground">
            {previewDescription}
          </span>
        )}
        {removals.length > 0 && (
          <ul
            className="flex max-w-[300px] flex-col gap-0.5 pl-4 text-xs text-muted-foreground"
            data-testid="history-removals"
          >
            {removals.slice(0, MAX_REMOVALS_SHOWN).map((removal, index) => (
              <li
                key={`${index}-${removal}`}
                className="flex items-center gap-1"
              >
                <ForwardedIconComponent
                  name="Trash2"
                  className="h-3 w-3 shrink-0"
                />
                <span className="truncate">{removal}</span>
              </li>
            ))}
            {removals.length > MAX_REMOVALS_SHOWN && (
              <li className="pl-4">
                {t("flowHistory.highlight.moreRemoved", {
                  count: removals.length - MAX_REMOVALS_SHOWN,
                })}
              </li>
            )}
          </ul>
        )}
      </CanvasBadge>

      {isPreviewLoading && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="pointer-events-auto flex items-center gap-2 rounded-lg border bg-background px-4 py-2 shadow-lg">
            <ForwardedIconComponent
              name="Loader2"
              className="h-4 w-4 animate-spin text-muted-foreground"
            />
            <span className="text-sm text-muted-foreground">
              {t("version.loadingPreview")}
            </span>
          </div>
        </div>
      )}

      {previewLabel === "Current Draft" && (
        <SaveSnapshotButton flowId={currentFlowId} />
      )}

      {previewRevision !== null && (
        <>
          <RestoreRevisionButton
            flowId={currentFlowId}
            revision={previewRevision}
            label={previewLabel}
            restorable={restorable}
          />
          <HistorySlider />
        </>
      )}

      {previewRevision === null &&
        previewId &&
        previewLabel &&
        previewLabel !== "Current Draft" && (
          <RestoreVersionButton
            flowId={currentFlowId}
            versionId={previewId}
            versionTag={previewLabel}
          />
        )}
    </div>
  );
}
