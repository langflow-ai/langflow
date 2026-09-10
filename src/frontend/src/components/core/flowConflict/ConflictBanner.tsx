import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";
import { CanvasBanner } from "./CanvasBanner";
import { LoadLatestDialog } from "./LoadLatestDialog";

/**
 * Tells someone their flow moved on without them, and offers the way forward.
 *
 * Deliberately a banner and not a modal: the person keeps reading and moving around
 * their own canvas while they decide. Taking the screen away would make a situation
 * where nothing is lost feel like one where something is.
 *
 * It belongs to the live canvas only. Version history is a read-only view of the
 * past, where its own overlay already owns the screen and a second one on top of it
 * left both unreadable — and where none of the actions it offers make sense.
 */
export function ConflictBanner({ flowId }: { flowId: string }) {
  const { t } = useTranslation();
  const conflict = useFlowConflictStore((state) => state.conflict);
  const openDialog = useFlowConflictStore((state) => state.openDialog);
  const previewingVersion = useVersionPreviewStore(
    (state) => state.previewLabel !== null,
  );
  const [loadLatestOpen, setLoadLatestOpen] = useState(false);

  if (!conflict || conflict.flowId !== flowId || previewingVersion) return null;

  const name = conflict.author.username || t("multiEdit.unknownAuthor");
  const title = conflict.isSelf
    ? t("multiEdit.banner.titleSelf")
    : t("multiEdit.banner.title", { name });
  const description = conflict.isSelf
    ? t("multiEdit.banner.descriptionSelf")
    : t("multiEdit.banner.description", { name });

  return (
    <>
      <CanvasBanner
        testId="flow-conflict-banner"
        tone="warning"
        icon="TriangleAlert"
        title={title}
        description={description}
        actions={
          <>
            <Button
              variant="conflictSecondary"
              size="banner"
              onClick={() => setLoadLatestOpen(true)}
              data-testid="flow-conflict-load-latest-button"
            >
              {t("multiEdit.banner.loadLatest")}
            </Button>
            <Button
              variant="conflictPrimary"
              size="banner"
              onClick={openDialog}
              data-testid="flow-conflict-review-button"
            >
              {t("multiEdit.banner.review")}
            </Button>
          </>
        }
      />
      <LoadLatestDialog
        flowId={flowId}
        open={loadLatestOpen}
        onOpenChange={setLoadLatestOpen}
      />
    </>
  );
}

/** The amber glow that marks the whole canvas as no longer saving. */
export function ConflictCanvasFrame({ flowId }: { flowId: string }) {
  const conflict = useFlowConflictStore((state) => state.conflict);
  const previewingVersion = useVersionPreviewStore(
    (state) => state.previewLabel !== null,
  );
  if (!conflict || conflict.flowId !== flowId || previewingVersion) return null;

  return (
    <div
      aria-hidden="true"
      data-testid="flow-conflict-frame"
      className="flow-conflict-overlay pointer-events-none absolute inset-0 z-40"
    />
  );
}

export default ConflictBanner;
