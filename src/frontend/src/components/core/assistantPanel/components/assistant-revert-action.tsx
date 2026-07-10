import { Check, RotateCcw } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAssistantRevert } from "../hooks/use-assistant-revert";

interface AssistantRevertActionProps {
  /** Version id snapshotted BEFORE this message's canvas edits. */
  restoreVersionId: string;
  /** True once this message's restore point was already applied. */
  reverted: boolean;
  /** Persists the reverted state on the message after a successful revert. */
  onReverted: () => void;
}

/**
 * Footer action on the latest assistant message that carries a restore
 * point: "Revert this edit" opens a confirmation dialog, then snapshots
 * the current state and restores the pre-edit version. After success the
 * action becomes a disabled "Reverted" marker for the session.
 */
export function AssistantRevertAction({
  restoreVersionId,
  reverted,
  onReverted,
}: AssistantRevertActionProps) {
  const { t } = useTranslation();
  const [showConfirm, setShowConfirm] = useState(false);
  const { revert, isReverting } = useAssistantRevert();

  if (reverted) {
    return (
      <div
        data-testid="assistant-revert-reverted"
        className="mt-2 flex w-fit items-center gap-1.5 text-xs text-muted-foreground"
      >
        <Check className="h-3.5 w-3.5" />
        <span>{t("assistant.revert.reverted")}</span>
      </div>
    );
  }

  const handleConfirm = async () => {
    await revert(restoreVersionId, { onSuccess: onReverted });
    setShowConfirm(false);
  };

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        data-testid="assistant-revert-button"
        className="mt-2 h-6 w-fit gap-1.5 px-2 text-xs text-muted-foreground"
        onClick={() => setShowConfirm(true)}
        disabled={isReverting}
      >
        <RotateCcw className="h-3.5 w-3.5" />
        {t("assistant.revert.action")}
      </Button>
      <Dialog
        open={showConfirm}
        onOpenChange={(next) => {
          if (!next && !isReverting) setShowConfirm(false);
        }}
      >
        <DialogContent
          className="max-w-md"
          data-testid="assistant-revert-confirm"
        >
          <DialogHeader>
            <DialogTitle>{t("assistant.revert.confirmTitle")}</DialogTitle>
            <DialogDescription>
              {t("assistant.revert.confirmBody")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              data-testid="assistant-revert-cancel"
              onClick={() => setShowConfirm(false)}
              disabled={isReverting}
            >
              {t("assistant.revert.cancel")}
            </Button>
            <Button
              size="sm"
              data-testid="assistant-revert-confirm-button"
              onClick={handleConfirm}
              loading={isReverting}
            >
              {t("assistant.revert.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
