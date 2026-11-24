import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

type FooterProps = {
  isPending: boolean;
  /** How many contested components still have no answer. */
  unresolvedConflicts: number;
  isForking: boolean;
  isOverwriting: boolean;
  isLoadingLatest: boolean;
  onCancel: () => void;
  onLoadLatest: () => void;
  onDuplicate: () => void;
  onOverwrite: () => void;
};

/**
 * The ways out of the review, and the one that asks twice.
 *
 * Loading the latest version throws away both the selection above and the
 * unsaved canvas behind it, so it confirms in place: the band it replaces is
 * the one the reader was already looking at.
 */
export function ConflictDialogFooter({
  isPending,
  unresolvedConflicts,
  isForking,
  isOverwriting,
  isLoadingLatest,
  onCancel,
  onLoadLatest,
  onDuplicate,
  onOverwrite,
}: FooterProps) {
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  // Writing the original is the one exit that overwrites somebody else, so it
  // stays shut until every contested component has been answered. Duplicating
  // is left open on purpose: it is the way out for a reader who cannot decide,
  // and it costs nobody their work.
  const blocked = unresolvedConflicts > 0;

  if (confirming) {
    return (
      <div
        className="flex flex-col gap-3 border-t border-muted px-5 py-4"
        data-testid="load-latest-confirm"
      >
        <div className="flex items-start gap-3">
          <ForwardedIconComponent
            name="TriangleAlert"
            className="mt-0.5 h-4 w-4 shrink-0 text-destructive"
            aria-hidden="true"
          />
          <div className="flex min-w-0 flex-col gap-1">
            <p className="text-[13px] font-semibold leading-[19.5px] text-foreground">
              {t("multiEdit.loadLatest.title")}
            </p>
            <p className="text-xs leading-[18px] text-muted-foreground">
              {t("multiEdit.loadLatest.description")}
            </p>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="conflictQuiet"
            size="dialogAction"
            onClick={() => setConfirming(false)}
            disabled={isPending}
          >
            {t("multiEdit.loadLatest.cancel")}
          </Button>
          <Button
            variant="destructive"
            size="dialogAction"
            loading={isLoadingLatest}
            onClick={onLoadLatest}
            data-testid="load-latest-confirm-button"
          >
            <ForwardedIconComponent name="RefreshCw" aria-hidden="true" />
            {t("multiEdit.loadLatest.confirm")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 border-t border-muted px-5 py-4">
      {blocked && (
        <p
          className="text-xs leading-[18px] text-accent-amber-foreground"
          data-testid="conflict-blocked-hint"
        >
          {t("multiEdit.dialog.resolveFirst", { count: unresolvedConflicts })}
        </p>
      )}
      <div className="flex items-center justify-between">
        <Button
          variant="conflictQuiet"
          size="dialogAction"
          onClick={onCancel}
          disabled={isPending}
        >
          {t("multiEdit.dialog.cancel")}
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="conflictQuiet"
            size="dialogAction"
            onClick={() => setConfirming(true)}
            disabled={isPending}
            data-testid="dialog-load-latest-button"
          >
            <ForwardedIconComponent name="RefreshCw" aria-hidden="true" />
            {t("multiEdit.dialog.loadLatest")}
          </Button>
          <Button
            variant="conflictSecondary"
            size="dialogAction"
            onClick={onDuplicate}
            disabled={isPending}
            data-testid="confirm-duplicate-flow"
          >
            <ForwardedIconComponent name="GitBranch" aria-hidden="true" />
            {isForking
              ? t("multiEdit.dialog.duplicating")
              : t("multiEdit.dialog.confirm")}
          </Button>
          <Button
            variant="conflictPrimary"
            size="dialogAction"
            onClick={onOverwrite}
            disabled={isPending || blocked}
            // Named rather than left to the reader to infer from a dead button.
            title={
              blocked
                ? t("multiEdit.dialog.resolveFirst", {
                    count: unresolvedConflicts,
                  })
                : undefined
            }
            data-testid="confirm-overwrite-flow"
          >
            {isOverwriting
              ? t("multiEdit.dialog.overwriting")
              : t("multiEdit.dialog.overwrite")}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ConflictDialogFooter;
