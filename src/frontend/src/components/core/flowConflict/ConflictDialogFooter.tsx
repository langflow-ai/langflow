import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

type FooterProps = {
  /** Sentence stating what the two exits will carry. */
  summary: string;
  /** How many of the person's own changes discarding would drop. */
  ownChangeCount: number;
  confirmingDiscard: boolean;
  setConfirmingDiscard: (confirming: boolean) => void;
  isPending: boolean;
  isForking: boolean;
  isOverwriting: boolean;
  isDiscarding: boolean;
  onCancel: () => void;
  onDiscard: () => void;
  onDuplicate: () => void;
  onOverwrite: () => void;
};

/**
 * The three ways out, and the one that asks twice.
 *
 * Its own file because the dialog above it is already at the size limit, and
 * because the confirmation state belongs to the choice, not to the diff.
 */
export function ConflictDialogFooter({
  summary,
  ownChangeCount,
  confirmingDiscard,
  setConfirmingDiscard,
  isPending,
  isForking,
  isOverwriting,
  isDiscarding,
  onCancel,
  onDiscard,
  onDuplicate,
  onOverwrite,
}: FooterProps) {
  const { t } = useTranslation();

  if (confirmingDiscard) {
    return (
      <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">
            {t("multiEdit.dialog.discardTitle")}
          </p>
          <p className="text-mmd text-muted-foreground">
            {t("multiEdit.dialog.discardHint", { count: ownChangeCount })}
          </p>
        </div>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => setConfirmingDiscard(false)}
            disabled={isPending}
          >
            {t("multiEdit.dialog.cancel")}
          </Button>
          <Button
            variant="destructive"
            onClick={onDiscard}
            disabled={isPending}
            data-testid="confirm-discard-my-changes"
            ignoreTitleCase
          >
            {t("multiEdit.dialog.discardConfirm")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 pt-2">
      <p className="text-mmd text-muted-foreground">{summary}</p>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="outline" onClick={onCancel} disabled={isPending}>
          {t("multiEdit.dialog.cancel")}
        </Button>
        <Button
          variant="outline"
          onClick={() => setConfirmingDiscard(true)}
          disabled={isPending || isDiscarding}
          data-testid="discard-my-changes"
          className="gap-2"
        >
          <ForwardedIconComponent
            name="RotateCcw"
            className="h-4 w-4"
            aria-hidden="true"
          />
          {t("multiEdit.dialog.discard")}
        </Button>
        <Button
          variant="outline"
          onClick={onDuplicate}
          disabled={isPending}
          data-testid="confirm-duplicate-flow"
          className="gap-2"
        >
          <ForwardedIconComponent
            name="Copy"
            className="h-4 w-4"
            aria-hidden="true"
          />
          {isForking
            ? t("multiEdit.dialog.duplicating")
            : t("multiEdit.dialog.confirm")}
        </Button>
        <Button
          onClick={onOverwrite}
          disabled={isPending}
          data-testid="confirm-overwrite-flow"
          className="gap-2"
        >
          <ForwardedIconComponent
            name="Check"
            className="h-4 w-4"
            aria-hidden="true"
          />
          {isOverwriting
            ? t("multiEdit.dialog.overwriting")
            : t("multiEdit.dialog.overwrite")}
        </Button>
      </div>
    </div>
  );
}

export default ConflictDialogFooter;
