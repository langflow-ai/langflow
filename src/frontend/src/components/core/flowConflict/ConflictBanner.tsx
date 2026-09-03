import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";

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

  if (!conflict || conflict.flowId !== flowId || previewingVersion) return null;

  const name = conflict.author.username || t("multiEdit.unknownAuthor");
  const title = conflict.isSelf
    ? t("multiEdit.banner.titleSelf")
    : t("multiEdit.banner.title", { name });
  const description = conflict.isSelf
    ? t("multiEdit.banner.descriptionSelf")
    : t("multiEdit.banner.description", { name });

  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-6 z-50 flex justify-center px-6"
      data-testid="flow-conflict-banner"
    >
      <div
        role="status"
        className="pointer-events-auto flex w-full max-w-3xl items-center gap-4 rounded-xl border border-accent-amber-foreground/40 bg-background px-5 py-4 shadow-lg"
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-amber">
          <ForwardedIconComponent
            name="TriangleAlert"
            className="h-5 w-5 text-accent-amber-foreground"
            aria-hidden="true"
          />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="text-mmd text-muted-foreground">{description}</p>
        </div>
        <Button
          size="sm"
          onClick={openDialog}
          data-testid="flow-conflict-review-button"
          className="shrink-0 gap-2"
        >
          <ForwardedIconComponent
            name="GitCompare"
            className="h-4 w-4"
            aria-hidden="true"
          />
          {t("multiEdit.banner.review")}
        </Button>
      </div>
    </div>
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
