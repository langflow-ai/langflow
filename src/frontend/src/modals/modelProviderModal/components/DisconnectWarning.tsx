import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface DisconnectWarningProps {
  show: boolean;
  message: string;
  onCancel: () => void;
  onConfirm: () => void;
  isLoading: boolean;
  className?: string;
}

const DisconnectWarning = ({
  show,
  message,
  onCancel,
  onConfirm,
  isLoading,
  className,
}: DisconnectWarningProps) => {
  const { t } = useTranslation();

  return (
    <Dialog
      open={show}
      onOpenChange={(open) => {
        if (!open) {
          onCancel();
        }
      }}
    >
      <DialogContent
        hideCloseButton
        className={className}
        onOpenAutoFocus={(e) => {
          // Move focus to Cancel (least destructive action) on open.
          e.preventDefault();
          const cancelButton = (e.currentTarget as HTMLElement).querySelector(
            '[data-testid="disconnect-warning-cancel"]',
          ) as HTMLElement | null;
          cancelButton?.focus();
        }}
      >
        <DialogHeader>
          <DialogTitle className="text-destructive flex items-center gap-1 text-md">
            <ForwardedIconComponent
              name="Circle"
              className="text-destructive w-3 h-3 fill-destructive mr-2 animate-pulse"
              ariaHidden
            />
            {t("modelProviders.warning")}
          </DialogTitle>
        </DialogHeader>

        <DialogDescription className="text-sm text-foreground">
          {message}
        </DialogDescription>

        <DialogFooter>
          <Button
            size="sm"
            variant="ghost"
            onClick={onCancel}
            data-testid="disconnect-warning-cancel"
          >
            {t("modelProviders.cancelButton")}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={onConfirm}
            loading={isLoading}
            data-testid="disconnect-warning-confirm"
          >
            {t("modelProviders.confirmButton")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default DisconnectWarning;
