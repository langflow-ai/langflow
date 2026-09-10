import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

type FooterProps = {
  isPending: boolean;
  isForking: boolean;
  isOverwriting: boolean;
  onCancel: () => void;
  onDuplicate: () => void;
  onOverwrite: () => void;
};

/**
 * The two exits that carry the selection above, and the way out that carries none.
 *
 * Leaving sits apart from the two commitments so the reader never lands on it by
 * aiming for one of them. Taking the other version outright is not offered here
 * at all: it discards the selection this dialog exists to make, and already has
 * its own confirmation off the banner.
 */
export function ConflictDialogFooter({
  isPending,
  isForking,
  isOverwriting,
  onCancel,
  onDuplicate,
  onOverwrite,
}: FooterProps) {
  const { t } = useTranslation();

  return (
    <div className="flex items-center justify-between border-t border-muted px-5 py-4">
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
          disabled={isPending}
          data-testid="confirm-overwrite-flow"
        >
          {isOverwriting
            ? t("multiEdit.dialog.overwriting")
            : t("multiEdit.dialog.overwrite")}
        </Button>
      </div>
    </div>
  );
}

export default ConflictDialogFooter;
