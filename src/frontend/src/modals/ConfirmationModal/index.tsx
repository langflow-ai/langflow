import { useState } from "react";
import { Button } from "../../components/ui/button";
import { ConfirmationModalType } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";
import BaseModal from "../baseModal";

export default function ConfirmationModal({
  title,
  asChild,
  titleHeader,
  modalContent,
  modalContentTitle,
  cancelText,
  confirmationText,
  children,
  icon,
  data,
  index,
  onConfirm,
}: ConfirmationModalType) {
  const Icon: any = nodeIconsLucide[icon];

  const [open, setOpen] = useState(false);
  return (
    <BaseModal size="x-small" open={open} setOpen={setOpen}>
      <BaseModal.Trigger asChild={asChild}>{children}</BaseModal.Trigger>
      <BaseModal.Header description={titleHeader}>
        <span className="pr-2">{title}</span>
        <Icon
          name="icon"
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        {modalContentTitle != "" && (
          <>
            <strong>{modalContentTitle}</strong>
            <br></br>
          </>
        )}
        <span>{modalContent}</span>
      </BaseModal.Content>

      <BaseModal.Footer>
        <Button
          className="ml-3"
          onClick={() => {
            setOpen(false);
            onConfirm(index, data);
          }}
        >
          {confirmationText}
        </Button>

        <Button
          variant="outline"
          onClick={() => {
            setOpen(false);
          }}
        >
          {cancelText}
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
